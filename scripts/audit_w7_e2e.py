"""Đối chiếu receipts E2E #149 bằng kết nối DB mới; chỉ đọc DB/Qdrant."""

import argparse
import base64
from contextlib import closing
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import traceback
from urllib.parse import urlsplit
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def results(suites):
    for suite in suites:
        for spec in suite.get("specs", []):
            for test in spec["tests"]:
                yield spec["title"], test
        yield from results(suite.get("suites", []))


def audit(report_path, input_path, qdrant_url, output):
    from qdrant_client import QdrantClient
    from sqlalchemy import create_engine, func, make_url, select
    from sqlalchemy.orm import Session
    from app.models import Asset, Feedback, SearchEvent
    from app.search.index_manifest import load_index_manifest

    url = make_url(os.environ["TEST_DATABASE_URL"])
    target = urlsplit(qdrant_url)
    if (url.drivername != "postgresql+psycopg" or not (url.database or "").startswith("test_issue149_")
            or url.host not in {"localhost", "127.0.0.1"}
            or target.scheme != "http" or target.hostname not in {"localhost", "127.0.0.1"}
            or target.username or target.password or target.path not in {"", "/"} or target.query or target.fragment):
        raise ValueError("Chỉ audit target local riêng của #149.")
    raw = report_path.read_bytes()
    report = json.loads(raw)
    inputs = json.loads(input_path.read_text(encoding="utf-8"))
    manifest = load_index_manifest(input_path.parent / "text-index-manifest.json")
    events, receipts, cases = {}, {}, []
    for title, test in results(report["suites"]):
        cases.append(dict(title=title, project=test["projectName"], status=test["status"],
                          attempts=[dict(status=r["status"], duration_ms=r["duration"]) for r in test["results"]]))
        for result in test["results"]:
            for attachment in result.get("attachments", []):
                if attachment["name"] not in {"stack-http-observations", "direct-feedback-receipt"}:
                    continue
                value = json.loads(base64.b64decode(attachment["body"]))
                if attachment["name"] == "direct-feedback-receipt":
                    receipts[value["feedback_id"]] = value
                else:
                    for observation in value:
                        body = observation.get("body")
                        if (observation.get("status") == 200 and observation["path"] in
                                {"/api/v1/search/text", "/api/v1/search/image"}):
                            events[body["search_event_id"]] = body
                        if observation.get("status") == 201 and observation["path"] == "/api/v1/feedback":
                            receipts[body["feedback_id"]] = body
    if not events or not receipts:
        raise ValueError("Report cần search events và feedback receipts thật để audit.")
    engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection, connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            with Session(bind=connection) as session:
                for event_id, body in events.items():
                    event = session.get(SearchEvent, UUID(event_id))
                    assert event is not None
                    assert event.result_asset_ids == [row["asset"]["asset_id"] for row in body["results"]]
                    assert all(getattr(event, key) == value for key, value in body["versions"].items())
                    assert (event.query_text if event.query_type == "text" else event.query_image_ref) == body["query"]
                    expected = inputs["text_versions" if event.query_type == "text" else "image_versions"]
                    assert body["versions"] == expected
                    filters = event.filters
                    for row in body["results"]:
                        asset = row["asset"]
                        for key in ("category", "license"):
                            if filters.get(key) is not None:
                                assert asset[key] == filters[key]
                        if filters.get("format") is not None:
                            assert filters["format"] in asset["formats"]
                        if filters.get("face_count_min") is not None:
                            assert asset["face_count"] >= filters["face_count_min"]
                        if filters.get("face_count_max") is not None:
                            assert asset["face_count"] <= filters["face_count_max"]
                for receipt in receipts.values():
                    feedback = session.get(Feedback, UUID(receipt["feedback_id"]))
                    assert feedback is not None
                    assert str(feedback.search_event_id) == receipt["search_event_id"]
                    assert feedback.asset_id == receipt["asset_id"] and feedback.relevance == receipt["relevance"]
                    assert receipt["storage"] == "postgresql" and receipt["mock"] is False
                    event = session.get(SearchEvent, feedback.search_event_id)
                    assert event is not None and feedback.asset_id in event.result_asset_ids
                counts = {model.__tablename__: session.scalar(select(func.count()).select_from(model))
                          for model in (Asset, SearchEvent, Feedback)}
                assert counts["assets"] == inputs["asset_count"]
    finally:
        engine.dispose()
    with closing(QdrantClient(url=qdrant_url, timeout=10)) as client:
        store = manifest.make_store(client)
        store.validate_collection()
        point_count = client.count(manifest.collection, exact=True).count
        assert point_count == manifest.point_count == inputs["asset_count"]
        points, cursor = client.scroll(manifest.collection, limit=256, with_payload=True, with_vectors=False)
        assert cursor is None and len(points) == point_count
        assert {point.payload["asset_id"] for point in points} == {
            row["asset_id"] for row in json.loads((input_path.parent / manifest.source_manifest).read_text(encoding="utf-8"))}
        assert all(point.payload["_index"] == {**asdict(manifest.as_index_config()), "distance": "Cosine"} for point in points)
    value = dict(status="persistence_verified", report_sha256=sha256(raw).hexdigest(),
                 stats=report["stats"], cases=cases, observed_search_events_verified=len(events),
                 feedback_receipts_verified=len(receipts), database_counts=counts,
                 qdrant=dict(collection=manifest.collection, point_count=point_count, payload_versions_verified=True),
                 receipt_ids=list(receipts), note="Audit persistence không biến E2E thất bại thành đạt.")
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({key: value[key] for key in ("status", "observed_search_events_verified", "feedback_receipts_verified", "database_counts")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--qdrant-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        audit(args.report, args.input, args.qdrant_url, args.output)
    except Exception as error:
        frame = traceback.extract_tb(error.__traceback__)[-1]
        print(json.dumps({"status": "failed", "error_type": type(error).__name__,
                          "error_file": Path(frame.filename).name, "error_line": frame.lineno}))
        raise SystemExit(1)
