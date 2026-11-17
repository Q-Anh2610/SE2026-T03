"""#118: một app/DB thật cho search/image/feedback/admin/reindex và browser sản phẩm."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def verify(args, report):
    import httpx
    from PIL import Image
    from qdrant_client import QdrantClient
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from app.core.config import Settings
    from app.main import create_app
    from app.models import Asset, Feedback, SearchEvent
    from app.ingestion.source_adapter import SourceAdapter
    from app.search.index_manifest import load_index_manifest
    from app.search.image_index_manifest import load_image_index_manifest
    from scripts.asset_api_test_support import isolated_asset_database
    from scripts.verify_jobs_api import http_server
    from scripts.verify_text_search_api import fingerprint

    text_manifest = load_index_manifest(args.text_index_root / "index-manifest.json")
    image_manifest = load_image_index_manifest(args.image_index_root / "index-manifest.json")
    text_manifest.verify_input_hashes(args.text_index_root)
    image_manifest.verify_input_hashes(args.image_input_root)
    assert text_manifest.source_manifest_sha256 == image_manifest.source_manifest_sha256
    baselines = [(args.text_index_root, text_manifest), (args.image_index_root, image_manifest)]
    fingerprints = []
    for root, manifest in baselines:
        with closing(QdrantClient(path=str(root / "qdrant"))) as client:
            fingerprints.append(fingerprint(client, manifest.collection))
    adapter = SourceAdapter(args.text_index_root / text_manifest.source_manifest)
    metadata, invalid = adapter.normalize_and_validate(adapter.load_manifest())
    assert not invalid and len(metadata) == text_manifest.asset_count
    image_ready = json.loads((args.image_input_root / image_manifest.ready_manifest).read_text(encoding="utf-8"))
    key = secrets.token_urlsafe(32)
    headers = {"X-Admin-Key": key}
    with isolated_asset_database(os.environ.get("TEST_DATABASE_URL", "")) as db, TemporaryDirectory(prefix="w5-integration-") as temp:
        db.migrate()
        with Session(db.engine) as session, session.begin():
            session.add_all(Asset(**row) for row in metadata)
        directory = Path(temp)
        query = directory / "query.png"
        with Image.open(args.image_input_root / image_ready[0]["image_path"]) as image:
            image.convert("RGB").save(query, format="PNG")
        ui_port = free_port()
        settings = Settings(_env_file=None, env="test", mock_api_enabled=False,
            text_search_source="service", text_index_manifest=args.text_index_root / "index-manifest.json",
            text_index_root=args.text_index_root, text_qdrant_local_path=args.text_index_root / "qdrant",
            image_search_source="service", image_index_manifest=args.image_index_root / "index-manifest.json",
            image_index_root=args.image_input_root, image_qdrant_local_path=args.image_index_root / "qdrant",
            feedback_source="database", admin_api_key=key, reindex_enabled=True,
            reindex_cache_ready=args.text_index_root / "ready.json", reindex_output_root=args.output_root,
            cors_origins=[f"http://127.0.0.1:{ui_port}"])
        app = create_app(settings)
        app.state.db_engine = db.engine
        expected = {"text": text_manifest.execution_versions().model_dump(),
                    "image": {**image_manifest.execution_versions().model_dump(),
                              "config_version": "image-exact-all-filtered-rgb-v1-k200"}}
        browser_reports = []
        report["browser"] = browser_reports
        with http_server(app, startup_timeout=180, shutdown_timeout=180) as origin:
            try:
                vite_env = dict(os.environ, VITE_API_BASE_URL=origin)
                vite = subprocess.Popen(["node", str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
                    "--host", "127.0.0.1", "--port", str(ui_port), "--strictPort", "--mode", "api"],
                    cwd=ROOT / "frontend", env=vite_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    ui_url = f"http://127.0.0.1:{ui_port}"
                    deadline = time.monotonic() + 45
                    while True:
                        try:
                            if httpx.get(ui_url, timeout=2).status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        if vite.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError("Vite startup failed.")
                        time.sleep(.2)

                    def browser(failed_job=None):
                        path = directory / ("browser-failed.json" if failed_job else "browser-live.json")
                        environment = dict(os.environ, W5_UI_URL=ui_url, W5_API_URL=origin, W5_ADMIN_KEY=key,
                            W5_IMAGE_QUERY=str(query), W5_BROWSER_REPORT=str(path))
                        environment.pop("W5_FAILED_JOB_ID", None)
                        if failed_job:
                            environment["W5_FAILED_JOB_ID"] = failed_job
                        completed = subprocess.run(["node", str(ROOT / "scripts/verify_w5_browser.mjs")],
                            cwd=ROOT, env=environment, timeout=600, check=False)
                        data = json.loads(path.read_text(encoding="utf-8"))
                        browser_reports.append(data)
                        if completed.returncode or data["status"] != "passed":
                            raise RuntimeError("Live browser integration failed.")
                        return data

                    first_browser = browser()
                    job_id = first_browser["job_id"]
                    with httpx.Client(base_url=origin, timeout=90) as api:
                        def count(model):
                            with Session(db.engine) as reader:
                                return reader.scalar(select(func.count()).select_from(model))

                        def text_search():
                            response = api.post("/api/v1/search/text", json={"query": "wooden chair", "limit": 12})
                            assert response.status_code == 200
                            body = response.json()
                            assert body["versions"] == expected["text"] and body["mock"] is False
                            return body

                        def rating(body, asset=None):
                            return api.post("/api/v1/feedback", json={"search_event_id": body["search_event_id"],
                                "asset_id": asset or body["results"][0]["asset"]["asset_id"], "relevance": True})

                        def wait(identifier):
                            deadline = time.monotonic() + 120
                            while time.monotonic() < deadline:
                                job = api.get(f"/api/v1/admin/jobs/{identifier}", headers=headers).json()["job"]
                                if job["status"] in ("failed", "succeeded"):
                                    report["jobs"].append(job)
                                    return job
                                time.sleep(.1)
                            raise RuntimeError("Failure job wait timed out.")

                        finished = wait(job_id)
                        assert finished["status"] == "succeeded" and finished["result"]["point_count"] == 200
                        assert api.get(f"/api/v1/admin/jobs/{uuid4()}", headers=headers).status_code == 404
                        assert api.post("/api/v1/search/text", json={"query": " "}).status_code == 400
                        sample = text_search()
                        outside = next(row["asset_id"] for row in metadata
                            if row["asset_id"] not in {r["asset"]["asset_id"] for r in sample["results"]})
                        rejected = rating(sample, outside)
                        assert rejected.status_code == 400 and rejected.json()["error"]["code"] == "EVENT_ASSET_MISMATCH"
                        baseline = count(Feedback)
                        with db.engine.begin() as connection:
                            connection.exec_driver_sql("ALTER TABLE feedbacks ADD CONSTRAINT w5_reject_feedback CHECK (false) NOT VALID")
                        try:
                            failed = rating(sample)
                            assert failed.status_code == 500 and count(Feedback) == baseline
                            assert text_search()["versions"] == expected["text"]
                            assert api.get(f"/api/v1/admin/jobs/{job_id}", headers=headers).status_code == 200
                        finally:
                            with db.engine.begin() as connection:
                                connection.exec_driver_sql("ALTER TABLE feedbacks DROP CONSTRAINT w5_reject_feedback")
                        assert rating(sample).status_code == 201
                        service = app.state.text_search_service
                        collection = service.service.store.collection_name
                        with service.lock:
                            service.service.store.collection_name = "__w5_missing_index__"
                        events_before = count(SearchEvent)
                        try:
                            failed = api.post("/api/v1/search/text", json={"query": "wooden chair"})
                            assert failed.status_code == 503 and count(SearchEvent) == events_before
                        finally:
                            with service.lock:
                                service.service.store.collection_name = collection
                        assert text_search()["versions"] == expected["text"]
                        wrong = directory / "invalid-cache.json"
                        wrong.write_text("[]", encoding="utf-8")
                        app.state.reindex_manager.settings = settings.model_copy(update={"reindex_cache_ready": wrong})
                        accepted = api.post("/api/v1/admin/reindex", headers=headers, json={"request_id": str(uuid4())})
                        assert accepted.status_code == 202
                        failed_job = wait(accepted.json()["job_id"])
                        assert failed_job["status"] == "failed" and failed_job["error"]["code"] == "INDEXING_FAILED"
                        assert text_search()["versions"] == expected["text"]
                        assert rating(text_search()).status_code == 201
                    browser(failed_job["job_id"])
                    # Đối chiếu HTTP từ browser với bản ghi DB thật, không chỉ tin UI.
                    with Session(db.engine) as reader:
                        for data in browser_reports:
                            for observed in data["search_events"]:
                                event = reader.get(SearchEvent, UUID(observed["event_id"]))
                                assert event.query_type == observed["kind"]
                                assert observed["versions"] == expected[observed["kind"]]
                                assert all(getattr(event, field) == value for field, value in observed["versions"].items())
                            for observed in data["feedbacks"]:
                                saved = reader.get(Feedback, UUID(observed["feedback_id"]))
                                assert str(saved.search_event_id) == observed["search_event_id"]
                                assert saved.asset_id == observed["asset_id"] and saved.relevance is True
                    report["browser"] = browser_reports
                    report["active_versions"] = expected
                    report["checks"] = ["browser_text_image_explanation_feedback", "browser_admin_auth_cancel_reindex_tracking",
                        "request_replay_conflict", "search_feedback_while_reindex_running_and_after_terminal",
                        "feedback_rollback_and_recovery", "missing_index_503_no_event_recovery",
                        "real_failed_child_and_failed_job_UI", "browser_records_verified_in_PostgreSQL"]
                finally:
                    vite.terminate()
                    vite.wait(timeout=15)
            finally:
                if app.state.reindex_manager is not None:
                    app.state.reindex_manager.close()  # Chờ worker trước khi helper dọn schema.
        output = args.output_root / str(UUID(job_id))
        manifest = load_index_manifest(output / "index-manifest.json")
        new_app = create_app(Settings(_env_file=None, env="test", mock_api_enabled=False,
            text_search_source="service", text_index_manifest=output / "index-manifest.json", text_index_root=output,
            text_qdrant_local_path=output / "qdrant", feedback_source="database"))
        new_app.state.db_engine = db.engine
        with http_server(new_app, startup_timeout=180, shutdown_timeout=180) as origin, httpx.Client(base_url=origin, timeout=90) as api:
            response = api.post("/api/v1/search/text", json={"query": "wooden chair", "limit": 12})
            assert response.status_code == 200
            body = response.json()
            assert body["versions"] == manifest.execution_versions().model_dump()
            assert body["versions"]["index_version"] == finished["result"]["index_version"]
            saved = api.post("/api/v1/feedback", json={"search_event_id": body["search_event_id"],
                "asset_id": body["results"][0]["asset"]["asset_id"], "relevance": False})
            assert saved.status_code == 201
            report["new_index_http_search_feedback"] = {"search_status": 200, "feedback_status": 201, "versions": body["versions"]}
        with Session(db.engine) as reader:
            report["event_count"] = reader.scalar(select(func.count()).select_from(SearchEvent))
            report["feedback_count"] = reader.scalar(select(func.count()).select_from(Feedback))
    for (root, manifest), before in zip(baselines, fingerprints, strict=True):
        with closing(QdrantClient(path=str(root / "qdrant"))) as client:
            assert fingerprint(client, manifest.collection) == before
    report.update(status="passed", baseline_fingerprints_unchanged=fingerprints,
                  baseline_asset_count=len(metadata), baseline_source_sha256=text_manifest.source_manifest_sha256,
                  active_index_changed=False)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-index-root", type=Path, required=True)
    parser.add_argument("--image-index-root", type=Path, required=True)
    parser.add_argument("--image-input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/processed/issue118/reindex")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/issue118/w5-http-browser.json")
    args = parser.parse_args()
    for field in ("text_index_root", "image_index_root", "image_input_root", "output_root"):
        setattr(args, field, getattr(args, field).resolve())
    result = {"issue": 118, "status": "running", "checks": [], "jobs": []}
    try:
        result = verify(args, result)
    except Exception as exc:
        import traceback
        result.update(status="failed", error_code=type(exc).__name__, locations=[
            {"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
            for frame in traceback.extract_tb(exc.__traceback__)])
    result["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["base_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result["working_tree_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    files = [Path(__file__), ROOT / "scripts/verify_w5_browser.mjs", ROOT / "scripts/verify_jobs_api.py",
             ROOT / "scripts/asset_api_test_support.py", *list((ROOT / "backend/app").rglob("*.py"))]
    result["module_sha256"] = {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in files}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"W5 #118: {result['status']}; report: {args.output}")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
