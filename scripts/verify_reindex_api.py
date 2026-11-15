"""#117: POST HTTP thật -> CLIP/index mới -> jobs/status -> HTTP search; DB test riêng."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def verify(args):
    import httpx
    from qdrant_client import QdrantClient
    from sqlalchemy.orm import Session
    from app.core.config import Settings
    from app.ingestion.source_adapter import SourceAdapter
    from app.main import create_app
    from app.models import Asset
    from app.search.index_manifest import load_index_manifest
    from app.services.reindex import SOURCE, SOURCE_HASH
    from scripts.asset_api_test_support import isolated_asset_database
    from scripts.verify_jobs_api import http_server
    from scripts.verify_text_search_api import fingerprint

    result = {"issue": 117, "status": "running", "jobs": []}
    baseline = load_index_manifest(args.baseline_index_root / "index-manifest.json")
    with closing(QdrantClient(path=str(args.baseline_index_root / "qdrant"))) as client:
        before = fingerprint(client, baseline.collection)
    key = secrets.token_urlsafe(32)
    headers = {"X-Admin-Key": key}
    with isolated_asset_database(os.environ.get("TEST_DATABASE_URL", "")) as db, TemporaryDirectory(prefix="reindex-smoke-") as temporary:
        db.migrate()
        adapter = SourceAdapter(SOURCE)
        metadata, invalid = adapter.normalize_and_validate(adapter.load_manifest())
        assert not invalid and len(metadata) == 200
        with Session(db.engine) as session, session.begin():
            session.add_all(Asset(**row) for row in metadata)
        settings = Settings(_env_file=None, env="test", mock_api_enabled=False, admin_api_key=key,
            reindex_enabled=True, reindex_cache_ready=args.cache_ready.resolve(),
            reindex_output_root=args.output_root.resolve(), text_search_source="mock", image_search_source="mock")
        app = create_app(settings)
        app.state.db_engine = db.engine

        def wait(api, identifier):
            deadline = time.monotonic() + settings.reindex_timeout_seconds + 30
            seen = set()
            while time.monotonic() < deadline:
                response = api.get(f"/api/v1/admin/jobs/{identifier}", headers=headers)
                assert response.status_code == 200
                job = response.json()["job"]
                seen.add(job["status"])
                if job["status"] in ("succeeded", "failed"):
                    result["jobs"].append(job)
                    return job, sorted(seen)
                time.sleep(.2)
            raise RuntimeError("Smoke wait timed out.")

        with http_server(app) as origin, httpx.Client(base_url=origin, timeout=30) as api:
            payload = {"request_id": str(uuid4()), "profile": "clip-candidate200-v1"}
            assert api.post("/api/v1/admin/reindex", json=payload).status_code == 403
            assert api.post("/api/v1/admin/reindex", headers=headers, json={**payload, "profile": "e5"}).status_code == 400
            accepted = api.post("/api/v1/admin/reindex", headers=headers, json=payload)
            assert accepted.status_code == 202
            identifier = accepted.json()["job_id"]
            replay = api.post("/api/v1/admin/reindex", headers=headers, json=payload)
            assert replay.status_code == 200 and replay.json()["job_id"] == identifier and replay.json()["reused"]
            assert api.post("/api/v1/admin/reindex", headers=headers, json={"request_id": str(uuid4())}).status_code == 409
            finished, observed = wait(api, identifier)
            assert finished["status"] == "succeeded", "Real reindex did not succeed."
            assert finished["result"]["point_count"] == finished["result"]["succeeded"] == 200
            assert finished["result"]["search_verified"] is True
            assert api.post("/api/v1/admin/reindex", headers=headers, json=payload).json()["job_id"] == identifier
            result["observed_states"] = observed
            result["accepted"] = accepted.json()
            # Fault injection vào cấu hình cache của worker trên app smoke riêng.
            # Child runner thật sẽ từ chối cache thiếu IDs; không sửa input gốc.
            wrong = Path(temporary) / "invalid-ready.json"
            wrong.write_text("[]", encoding="utf-8")
            app.state.reindex_manager.settings = settings.model_copy(update={"reindex_cache_ready": wrong})
            failed = api.post("/api/v1/admin/reindex", headers=headers, json={"request_id": str(uuid4())})
            assert failed.status_code == 202
            failed_job, _ = wait(api, failed.json()["job_id"])
            assert failed_job["status"] == "failed" and failed_job["error"]["code"] == "INDEXING_FAILED"
            assert app.state.settings.text_index_manifest is None
        output = args.output_root.resolve() / str(UUID(identifier))
        manifest = load_index_manifest(output / "index-manifest.json")
        manifest.verify_input_hashes(output)
        assert manifest.source_manifest_sha256 == SOURCE_HASH
        new_app = create_app(Settings(_env_file=None, env="test", mock_api_enabled=False,
            text_search_source="service", text_index_manifest=output / "index-manifest.json",
            text_index_root=output, text_qdrant_local_path=output / "qdrant"))
        new_app.state.db_engine = db.engine
        with http_server(new_app) as origin, httpx.Client(base_url=origin, timeout=90) as api:
            response = api.post("/api/v1/search/text", json={"query": "wooden chair", "limit": 12})
            assert response.status_code == 200
            body = response.json()
            assert body["mock"] is False and len(body["results"]) == 12
            assert body["versions"] == manifest.execution_versions().model_dump()
            assert body["versions"]["index_version"] == finished["result"]["index_version"]
            assert all(row["score_type"] == "cosine" for row in body["results"])
            result["search_after_reindex"] = {"status": 200, "result_count": 12, "versions": body["versions"]}
    with closing(QdrantClient(path=str(args.baseline_index_root / "qdrant"))) as client:
        assert fingerprint(client, baseline.collection) == before
    result.update(status="passed", original_index_fingerprint_unchanged=before,
                  source_sha256=SOURCE_HASH, active_index_changed=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-ready", type=Path, required=True)
    parser.add_argument("--baseline-index-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/processed/reindex")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/issue117/reindex-http.json")
    args = parser.parse_args()
    try:
        result = verify(args)
    except Exception as exc:
        import traceback
        result = {"status": "failed", "error_code": type(exc).__name__, "locations": [
            {"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
            for frame in traceback.extract_tb(exc.__traceback__)]}
    result["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["base_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result["working_tree_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    files = [Path(__file__), ROOT / "scripts/prepare_text_search_index.py", ROOT / "backend/app/services/reindex.py",
             ROOT / "backend/app/api/reindex.py", ROOT / "backend/app/models/job.py"]
    result["module_sha256"] = {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in files}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Reindex #117: {result['status']}; report: {args.output}")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
