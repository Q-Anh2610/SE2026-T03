"""HTTP image search #80 với CLIP/Qdrant thật và PostgreSQL test_* riêng."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import traceback
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from scripts.verify_text_search_api import fingerprint, verify


def check_image_http(app, db, text_manifest, metadata, origin, *, args):
    import httpx
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from app.models import SearchEvent
    from app.schemas.text_search import TextSearchFilters
    from app.search.image_index_manifest import load_image_index_manifest
    from app.search.image_search import ImageRetrievalConfig

    manifest = load_image_index_manifest(args.image_index_manifest)
    manifest.verify_input_hashes(args.image_index_root)
    assert manifest.source_manifest_sha256 == text_manifest.source_manifest_sha256
    ready = json.loads((args.image_index_root / manifest.ready_manifest).read_text(encoding="utf-8"))
    assert {r["metadata"]["asset_id"]: r["metadata"] for r in ready} == {r["asset_id"]: r for r in metadata}
    for row in ready:
        path = (args.image_index_root / row["image_path"]).resolve()
        assert path.is_relative_to(args.image_index_root.resolve())
        assert sha256(path.read_bytes()).hexdigest() == row["preview_sha256"]
    query = ready[0]
    content = (args.image_index_root / query["image_path"]).read_bytes()
    reference = "sha256:" + sha256(content).hexdigest()
    service = app.state.image_search_service
    assert service is not None
    expected_versions = manifest.execution_versions().model_dump()
    expected_versions["config_version"] = ImageRetrievalConfig.for_limit(200).config_version
    complete = next(r for r in metadata if r["category"] and r["license"] and r["formats"] and r["face_count"] is not None)
    filters = dict(category=complete["category"], license=complete["license"], format=complete["formats"][0],
        face_count_min=complete["face_count"], face_count_max=complete["face_count"])
    cases = [dict(page=page, limit=6) for page in (1, 2, 34, 35)]
    cases += [dict(filters=filters), dict(filters={"category": "__issue80_empty__"})]
    results = []
    successful = []

    def count():
        with Session(db.engine) as session:
            return session.scalar(select(func.count()).select_from(SearchEvent))

    def check_event(body, payload):
        with Session(db.engine) as session:
            event = session.get(SearchEvent, UUID(body["search_event_id"]))
            assert event.query_type == "image" and event.query_text is None
            assert event.query_image_ref == reference and event.filters == payload.get("filters", {})
            assert all(getattr(event, key) == value for key, value in body["versions"].items())

    with httpx.Client(base_url=origin, timeout=90) as client:
        def upload(payload):
            data = {key: str(value) for key, value in payload.items() if key != "filters"}
            data["filters"] = json.dumps(payload.get("filters", {}))
            return client.post("/api/v1/search/image", files={"image": ("preview.jpg", content)}, data=data)

        for payload in cases:
            direct = service.search_image(content, TextSearchFilters(**payload.get("filters", {})), candidate_limit=200)
            response = upload(payload)
            assert response.status_code == 200
            body = response.json()
            assert body["mock"] is False and body["query"] == reference
            assert body["versions"] == direct.versions.model_dump() == expected_versions
            assert body["query_id"] == body["search_event_id"]
            start = (payload.get("page", 1) - 1) * payload.get("limit", 12)
            hits = direct.hits[start:start + payload.get("limit", 12)]
            assert body["pagination"]["total"] == len(direct.hits)
            assert [r["asset"]["asset_id"] for r in body["results"]] == [h.asset_id for h in hits]
            assert [r["rank"] for r in body["results"]] == list(range(1, len(hits) + 1))
            for result, hit in zip(body["results"], hits):
                assert abs(result["score"] - hit.score) <= 1e-6
                assert result["retrieval_sources"] == ["clip_image_to_preview"]
                assert client.get("/api/v1/assets/" + hit.asset_id).json()["asset"] == result["asset"]
            check_event(body, payload)
            successful.append(body["search_event_id"])
            results.append(dict(payload=payload, total=len(direct.hits), hits=[h.model_dump() for h in hits],
                search_event_id=body["search_event_id"], status=200))
        first_two = [h["asset_id"] for row in results[:2] for h in row["hits"]]
        assert len(first_two) == len(set(first_two)) == 12
        baseline = count()
        errors = []
        store = service.service.store
        original_collection = store.collection_name
        with service.lock:
            store.collection_name = "__issue80_absent_index__"
        try:
            failed = upload({})
            assert failed.status_code == 503 and failed.json()["error"]["code"] == "SEARCH_UNAVAILABLE"
            errors.append(dict(case="missing_index", status=503, body=failed.json()))
        finally:
            with service.lock:
                store.collection_name = original_collection
        with db.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE search_events ADD CONSTRAINT issue80_reject_image CHECK (query_type <> 'image') NOT VALID")
        try:
            failed = upload({})
            assert failed.status_code == 500 and failed.json()["error"]["code"] == "INTERNAL_ERROR"
            assert not any(term in failed.text.lower() for term in ("postgresql", "password", "insert", "traceback", "issue80_reject"))
            errors.append(dict(case="db_write_failure", status=500, body=failed.json()))
        finally:
            with db.engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE search_events DROP CONSTRAINT issue80_reject_image")
        assert count() == baseline
        invalid = client.post("/api/v1/search/image", files={"image": ("broken.png", b"broken")})
        assert invalid.status_code == 400 and count() == baseline
        recovered = upload({})
        assert recovered.status_code == 200
        check_event(recovered.json(), {})
        assert count() == baseline + 1
    return dict(status="passed", versions=expected_versions, query_image_sha256=sha256(content).hexdigest(),
        cases=results, errors=errors, recovery_status=200, image_event_count=len(successful) + 1,
        final_event_count=count(), query_source="indexed_preview_self_match_diagnostic",
        image_source_manifest_sha256=manifest.source_manifest_sha256,
        image_ready_manifest_sha256=manifest.ready_manifest_sha256,
        limits="Backend real HTTP/local Qdrant/CLIP; frontend and image benchmark pending separate verification.")


def verify_image_http(args, *, extra_checks=None):
    from qdrant_client import QdrantClient
    from app.search.image_index_manifest import load_image_index_manifest

    manifest = load_image_index_manifest(args.image_index_manifest)
    assert (args.image_qdrant_local_path / "meta.json").is_file()
    with closing(QdrantClient(path=str(args.image_qdrant_local_path))) as client:
        before = fingerprint(client, manifest.collection)
        count = client.count(manifest.collection, exact=True).count

    def checks(*values):
        result = check_image_http(*values, args=args)
        if extra_checks is not None:
            result["feedback"] = extra_checks(*values)
        return result

    result = verify(args, extra_checks=checks)
    with closing(QdrantClient(path=str(args.image_qdrant_local_path))) as client:
        assert fingerprint(client, manifest.collection) == before
        assert client.count(manifest.collection, exact=True).count == count == manifest.point_count
    result["image_point_count"] = count
    result["image_persisted_fingerprint_before_after"] = before
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("index-manifest", "index-root", "qdrant-local-path",
                 "image-index-manifest", "image-index-root", "image-qdrant-local-path", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.settings_overrides = dict(image_search_source="service", image_index_manifest=args.image_index_manifest,
        image_index_root=args.image_index_root, image_qdrant_local_path=args.image_qdrant_local_path)
    try:
        result = verify_image_http(args)
    except Exception as exc:
        result = dict(status="failed", error_code=type(exc).__name__, failure_locations=[
            dict(file=Path(f.filename).name, line=f.lineno, function=f.name) for f in traceback.extract_tb(exc.__traceback__)])
    result["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["base_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    modules = [Path(__file__), ROOT / "scripts/verify_text_search_api.py"]
    modules += [p for p in (ROOT / "backend/app").rglob("*.py")
                if any(token in p.name for token in ("image_search", "text_search", "search_events"))]
    result["module_sha256"] = {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in modules}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Image API #80: {result['status']}; report: {args.output}")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
