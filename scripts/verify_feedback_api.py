"""Kiểm chứng #81 qua HTTP với search CLIP thật và DB test_* riêng."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import traceback
from hashlib import sha256
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from scripts.verify_image_search_api import verify_image_http


def check_feedback(app, db, manifest, metadata, origin):
    import httpx
    from sqlalchemy import func, select, text
    from sqlalchemy.orm import Session
    from app.models import Feedback, SearchEvent

    responses = []
    with httpx.Client(base_url=origin, timeout=60) as client:
        def send(event_id, asset_id, relevance=True):
            return client.post("/api/v1/feedback", json={
                "search_event_id": str(event_id), "asset_id": asset_id, "relevance": relevance,
            })

        def count():
            with Session(db.engine) as reader:
                return reader.scalar(select(func.count()).select_from(Feedback))

        with Session(db.engine) as reader:
            revision = reader.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == "0002"
            events = {kind: reader.scalar(select(SearchEvent).where(SearchEvent.query_type == kind,
                func.jsonb_array_length(SearchEvent.result_asset_ids) > 0).order_by(SearchEvent.created_at))
                for kind in ("text", "image")}
        assert all(events.values())
        for kind, event in events.items():
            for rating in (True, True, False):
                response = send(event.search_event_id, event.result_asset_ids[0], rating)
                assert response.status_code == 201
                body = response.json()
                assert body["mock"] is False and body["storage"] == "postgresql" and body["relevance"] is rating
                with Session(db.engine) as reader:
                    stored = reader.get(Feedback, UUID(body["feedback_id"]))
                    assert stored is not None and stored.search_event_id == event.search_event_id
                    assert stored.asset_id == event.result_asset_ids[0] and stored.relevance is rating
                    versions = {key: getattr(stored.search_event, key)
                        for key in ("model_version", "index_version", "config_version", "dataset_snapshot")}
                    assert versions == {key: getattr(event, key) for key in versions}
                responses.append(dict(query_type=kind, response=body, event_versions=versions))
        assert count() == len(responses) == len({row["response"]["feedback_id"] for row in responses}) == 6
        event = events["text"]
        outside = next(row["asset_id"] for row in metadata if row["asset_id"] not in event.result_asset_ids)
        errors = []
        for label, event_id, asset_id, expected_status, expected_code in (
            ("outside_page", event.search_event_id, outside, 400, "EVENT_ASSET_MISMATCH"),
            ("missing_event", uuid4(), outside, 404, "SEARCH_EVENT_NOT_FOUND"),
            ("missing_asset", event.search_event_id, "__issue81_missing__", 404, "ASSET_NOT_FOUND"),
        ):
            response = send(event_id, asset_id)
            assert response.status_code == expected_status and response.json()["error"]["code"] == expected_code
            errors.append(dict(case=label, status=response.status_code, body=response.json()))
        with Session(db.engine) as session, session.begin():
            legacy = SearchEvent(query_type="text", query_text="legacy-verification",
                **manifest.execution_versions().model_dump())
            session.add(legacy)
            session.flush()
            legacy_id = legacy.search_event_id
        response = send(legacy_id, outside)
        assert response.status_code == 400 and response.json()["error"]["code"] == "SEARCH_EVENT_RESULTS_UNAVAILABLE"
        errors.append(dict(case="legacy_event_unknown_results", status=400, body=response.json()))
        invalid = send(event.search_event_id, event.result_asset_ids[0], 1)
        assert invalid.status_code == 400 and invalid.json()["error"]["code"] == "INVALID_REQUEST"
        assert count() == 6
        with db.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE feedbacks ADD CONSTRAINT issue81_reject CHECK (false) NOT VALID")
        try:
            response = send(event.search_event_id, event.result_asset_ids[0])
            assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
            assert not any(token in response.text.lower() for token in ("insert", "postgresql", "traceback", "issue81_reject"))
            errors.append(dict(case="db_write_failure", status=500, body=response.json()))
        finally:
            with db.engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE feedbacks DROP CONSTRAINT issue81_reject")
        assert count() == 6
        recovery = send(event.search_event_id, event.result_asset_ids[0])
        assert recovery.status_code == 201 and count() == 7
    return dict(status="passed", migration_revision=revision, feedback_count=7,
        repeated_feedback_policy="append_new_record", checks=responses, errors=errors, recovery_status=201,
        limits="Local HTTP/CLIP/local Qdrant/PostgreSQL verification; frontend feedback E2E pending handoff.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("index-manifest", "index-root", "qdrant-local-path",
                 "image-index-manifest", "image-index-root", "image-qdrant-local-path", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.settings_overrides = dict(feedback_source="database", image_search_source="service",
        image_index_manifest=args.image_index_manifest, image_index_root=args.image_index_root,
        image_qdrant_local_path=args.image_qdrant_local_path)
    try:
        result = verify_image_http(args, extra_checks=check_feedback)
    except Exception as exc:
        result = dict(status="failed", error_code=type(exc).__name__, failure_locations=[
            dict(file=Path(f.filename).name, line=f.lineno, function=f.name) for f in traceback.extract_tb(exc.__traceback__)])
    result["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["base_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    modules = [Path(__file__), ROOT / "scripts/verify_image_search_api.py", ROOT / "scripts/verify_text_search_api.py"]
    modules += [p for p in (ROOT / "backend/app").rglob("*.py")
                if p.name in {"main.py", "config.py"} or any(k in p.name for k in ("feedback", "search_event", "text_search", "image_search"))]
    modules.append(ROOT / "backend/alembic/versions/0002_search_event_results.py")
    result["module_sha256"] = {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in modules}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Feedback #81: {result['status']}; report: {args.output}")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
