"""Kiểm chứng HTTP #65 với CLIP/Qdrant thật và PostgreSQL test_* riêng."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import socket
import sys
from threading import Thread
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def fingerprint(client, collection):
    points, offset = client.scroll(collection, limit=1000, with_payload=True, with_vectors=True)
    if offset is not None:
        raise ValueError("Verification script is limited to a subset below 1000 points.")
    rows = sorted([dict(id=str(p.id), payload=p.payload, vector=p.vector) for p in points], key=lambda x: x["id"])
    return sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def verify(args, *, configure_app=None, extra_checks=None):
    import httpx
    from pydantic import SecretStr
    from qdrant_client import QdrantClient
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    import uvicorn
    from app.core.config import Settings
    from app.ingestion.repository import upsert_downloaded_asset
    from app.ingestion.source_adapter import SourceAdapter
    from app.main import create_app
    from app.models import Asset, SearchEvent
    from app.search.index_manifest import load_index_manifest
    from scripts.asset_api_test_support import isolated_asset_database

    if not (args.qdrant_local_path / "meta.json").is_file():
        raise ValueError("Existing local index required.")
    manifest = load_index_manifest(args.index_manifest)
    manifest.verify_input_hashes(args.index_root)
    source = args.index_root / manifest.source_manifest
    adapter = SourceAdapter(source)
    metadata, invalid = adapter.normalize_and_validate(adapter.load_manifest())
    assert not invalid and len(metadata) == manifest.asset_count
    metadata_by_id = {row["asset_id"]: row for row in metadata}
    ready = json.loads((args.index_root / manifest.ready_manifest).read_text(encoding="utf-8"))
    assert len(ready) == len(metadata_by_id) and {r["metadata"]["asset_id"] for r in ready} == set(metadata_by_id)
    for row in ready:
        path = (args.index_root / row["image_path"]).resolve()
        assert path.is_relative_to(args.index_root.resolve())
        assert sha256(path.read_bytes()).hexdigest() == row["checksum"]
        assert row["metadata"] == metadata_by_id[row["metadata"]["asset_id"]]
    with closing(QdrantClient(path=str(args.qdrant_local_path))) as client:
        before_count = client.count(manifest.collection, exact=True).count
        before = fingerprint(client, manifest.collection)
    assert before_count == len(metadata)
    with isolated_asset_database(os.environ.get("TEST_DATABASE_URL", "")) as db:
        db.migrate()
        with Session(db.engine) as session, session.begin():
            for row in ready:
                upsert_downloaded_asset(session, row["metadata"], dict(checksum_resource="preview", checksum=row["checksum"],
                    preview_local_path=str(args.index_root / row["image_path"]),
                    preview_source_url=row["metadata"]["thumbnail_path"]))
        with Session(db.engine) as session:
            assert session.scalar(select(func.count()).select_from(Asset)) == len(metadata)
        settings = Settings(_env_file=None, env="test", mock_api_enabled=False, text_search_source="service",
            DATABASE_URL=SecretStr(db.url.render_as_string(hide_password=False)),
            text_index_manifest=args.index_manifest, text_index_root=args.index_root,
            text_qdrant_local_path=args.qdrant_local_path,
            cors_origins=getattr(args, "ui_origins", []),
            **getattr(args, "settings_overrides", {}))
        app = create_app(settings)
        app.state.db_engine = db.engine  # Chỉ cấp engine schema test, không mở DB nghiệp vụ.
        if configure_app is not None:
            configure_app(app, db)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False))
        thread = Thread(target=server.run, daemon=True)
        thread.start()
        events = []
        checks = []
        try:
            deadline = time.monotonic() + 180
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(.2)
            assert server.started, "HTTP server startup failed."
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=60) as client:
                assert client.get("/healthz").json() == {"status": "ok"}

                def search(payload):
                    response = client.post("/api/v1/search/text", json=payload)
                    assert response.status_code == 200, "Text search did not return HTTP 200."
                    body = response.json()
                    assert body["mock"] is False and body["versions"] == manifest.execution_versions().model_dump()
                    assert body["query_id"] == body["search_event_id"]
                    events.append((body["search_event_id"], payload))
                    for item in body["results"]:
                        assert item["asset"]["asset_id"] in metadata_by_id
                    return body

                first = search(dict(query="wooden chair", page=1, limit=12))
                second = search(dict(query="wooden chair", page=2, limit=12))
                assert first["pagination"]["total"] == second["pagination"]["total"] == min(200, len(metadata))
                ids = [x["asset"]["asset_id"] for body in (first, second) for x in body["results"]]
                assert len(ids) == len(set(ids)) == 24
                assert all([r["rank"] for r in b["results"]] == list(range(1, 13)) for b in (first, second))
                for result in first["results"][:3]:
                    assert client.get("/api/v1/assets/" + result["asset"]["asset_id"]).json()["asset"] == result["asset"]
                checks.append("live_http_pagination_unique_ids_detail")
                row = next(r for r in metadata if r["category"] and r["formats"] and r["face_count"] is not None)
                filters = dict(category=row["category"], license=row["license"], format=row["formats"][0],
                               face_count_min=row["face_count"], face_count_max=row["face_count"])
                filtered = search(dict(query="chair", filters=filters))
                assert filtered["results"]
                from app.schemas.text_search import TextSearchFilters
                from app.services.text_search import matches_database_filters
                from types import SimpleNamespace
                assert all(matches_database_filters(SimpleNamespace(**r["asset"]), TextSearchFilters(**filters))
                           for r in filtered["results"])
                checks.append("live_and_filters_inclusive_face_bounds")
                empty = search(dict(query="chair", filters={"category": "__issue65_missing_category__"}))
                assert empty["results"] == [] and empty["pagination"]["total"] == 0
                outside = search(dict(query="wooden chair", page=999))
                assert outside["results"] == []
                checks.append("live_empty_and_out_of_range_events")
                invalid = client.post("/api/v1/search/text", json={"query": " "})
                assert invalid.status_code == 400 and invalid.json()["error"]["code"] == "INVALID_REQUEST"
                checks.append("http_400_validation")
            with Session(db.engine) as session:
                assert session.scalar(select(func.count()).select_from(SearchEvent)) == len(events)
                for identifier, payload in events:
                    event = session.get(SearchEvent, UUID(identifier))
                    assert event.query_text == payload["query"] and event.filters == payload.get("filters", {})
                    assert all(getattr(event, key) == value for key, value in manifest.execution_versions().model_dump().items())
            checks.append("committed_events_match_actual_execution_versions")
            integration = extra_checks(app, db, manifest, metadata, f"http://127.0.0.1:{port}") if extra_checks else None
        finally:
            server.should_exit = True
            thread.join(30)
            if thread.is_alive():
                raise RuntimeError("HTTP server did not stop.")
    with closing(QdrantClient(path=str(args.qdrant_local_path))) as client:
        assert client.count(manifest.collection, exact=True).count == before_count
        assert fingerprint(client, manifest.collection) == before
    checks.append("persisted_qdrant_fingerprint_unchanged")
    return dict(status="passed", checks=checks, asset_count=len(metadata), point_count=before_count,
        event_count=len(events), manifest_sha256=manifest.source_manifest_sha256,
        versions=manifest.execution_versions().model_dump(), collection=manifest.collection,
        vector_name=manifest.vector_name, fingerprint_before_after=before,
        query="wooden chair", sample_ids=ids[:3], storage_mode="qdrant_persistent_local",
        platform=platform.platform(), python=platform.python_version(),
        integration=integration,
        limits="Backend HTTP/DB/CLIP/local-Qdrant smoke; frontend coverage recorded separately in integration; not server-mode Qdrant or quality benchmark.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-manifest", type=Path, required=True)
    parser.add_argument("--index-root", type=Path, required=True)
    parser.add_argument("--qdrant-local-path", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args)
    except Exception as exc:
        result = dict(status="failed", error_code=type(exc).__name__)
    result["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "data/processed/issue65" / ("http-" + uuid4().hex[:12] + ".json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Report: " + str(output))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")
    raise SystemExit(main())
