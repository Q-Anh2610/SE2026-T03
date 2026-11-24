"""#136: INSERT đạt nhưng deferred constraint lỗi tại COMMIT; HTTP/PG thật."""

from contextlib import contextmanager
from io import BytesIO
import json
import os

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models import Asset, Feedback, SearchEvent
from app.schemas.text_search import TextSearchCandidates
from scripts.asset_api_test_support import isolated_asset_database

pytestmark = pytest.mark.integration
KEY = "fixture-admin-key-136-not-a-real-secret"
VERSIONS = dict(model_version="fixture-model", index_version="fixture-index",
                config_version="fixture-config", dataset_snapshot="fixture-snapshot")


class FixtureRetrieval:
    def search_text(self, *_args, **_kwargs):
        return TextSearchCandidates(hits=[dict(asset_id="fixture-one", score=.5)], versions=VERSIONS)

    search_image = search_text


@pytest.fixture
def database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL test_* database.")
    with isolated_asset_database(value) as db:
        db.migrate()
        with Session(db.engine) as session, session.begin():
            session.add(Asset(asset_id="fixture-one", source="fixture", source_id="one",
                              name="Unchanged fixture", tags=[], formats=[]))
        yield db


def search(client, kind):
    if kind == "text":
        return client.post("/api/v1/search/text", json={"query": "fixture chair"})
    image = BytesIO()
    Image.new("RGB", (4, 4)).save(image, "PNG")
    return client.post("/api/v1/search/image", files={"image": ("fixture.png", image.getvalue())})


def counts(db):
    with Session(db.engine) as reader:
        return tuple(reader.scalar(select(func.count()).select_from(model))
                     for model in (SearchEvent, Feedback))


@contextmanager
def reject_at_commit(db, table):
    # Chỉ DDL trong schema UUID của fixture; không nhận tên bảng từ bên ngoài.
    assert table in {"search_events", "feedbacks"}
    with db.engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE FUNCTION fixture_reject_commit136() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'fixture-private-commit-detail'; RETURN NEW; END; $$
        """)
        connection.exec_driver_sql(f"""
            CREATE CONSTRAINT TRIGGER fixture_commit136 AFTER INSERT ON {table}
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION fixture_reject_commit136()
        """)
        assert connection.execute(text("""
            SELECT tgdeferrable AND tginitdeferred FROM pg_trigger
            WHERE tgrelid=to_regclass(:table) AND tgname='fixture_commit136'
        """), {"table": table}).scalar_one() is True
    inserted = []

    def after_insert(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().startswith("INSERT INTO " + table):
            inserted.append(True)

    event.listen(db.engine, "after_cursor_execute", after_insert)
    try:
        yield inserted
    finally:
        event.remove(db.engine, "after_cursor_execute", after_insert)
        with db.engine.begin() as connection:
            connection.exec_driver_sql(f"DROP TRIGGER fixture_commit136 ON {table}")
            connection.exec_driver_sql("DROP FUNCTION fixture_reject_commit136()")


@pytest.mark.parametrize("kind", ["text", "image", "feedback"])
def test_commit_time_failure_rolls_back_and_next_request_recovers(database, kind, caplog, monkeypatch):
    service = FixtureRetrieval()
    app = create_app(Settings(_env_file=None, env="test", mock_api_enabled=False,
        text_search_source="service", image_search_source="service", feedback_source="database",
        admin_api_key=KEY), text_search_service=service, image_search_service=service)
    app.state.db_engine = database.engine
    # Alembic fileConfig bỏ capture handler của pytest; chỉ gắn lại logger cần kiểm.
    import logging
    for name in ("app.services.feedback", "app.services.search_events", "app.db.dependencies", "app.request"):
        logger = logging.getLogger(name)
        monkeypatch.setattr(logger, "handlers", [*[h for h in logger.handlers if h is not caplog.handler], caplog.handler])
    with TestClient(app, raise_server_exceptions=False) as client:
        if kind == "feedback":
            event_id = search(client, "text").json()["search_event_id"]

            def request():
                return client.post("/api/v1/feedback", json={"search_event_id": event_id,
                    "asset_id": "fixture-one", "relevance": True})
        else:
            def request():
                return search(client, kind)

        before = counts(database)
        table = "feedbacks" if kind == "feedback" else "search_events"
        with reject_at_commit(database, table) as inserted:
            response = request()
            assert inserted, "INSERT must succeed before the deferred constraint fails at commit"
            assert response.status_code == 500
            assert response.json() == {"error": {"code": "INTERNAL_ERROR",
                "message": "Lỗi máy chủ. Vui lòng thử lại sau.", "details": []}}
            assert not any(value in response.text + caplog.text for value in (
                "fixture-private-commit-detail", "INSERT INTO", "fixture_reject_commit136", "Traceback"))
            identifier = response.headers["X-Request-ID"]
            traced = [json.loads(record.getMessage()) for record in caplog.records
                      if record.getMessage().startswith("{")]
            traced = [row for row in traced if row.get("request_id") == identifier]
            summary, = [row for row in traced if row["event"] == "request.completed"]
            expected_stage = "feedback_persistence" if kind == "feedback" else "search_event_persistence"
            assert (summary["status"], summary["error_code"], summary["stage"]) == (500, "INTERNAL_ERROR", expected_stage)
            assert any(row["event"] != "request.completed" and row["stage"] == expected_stage for row in traced)
            assert database.engine.pool.checkedout() == 0
            assert counts(database) == before
            # Các read requests độc lập vẫn hoạt động, không có dữ liệu ghi dở.
            assert client.get("/api/v1/assets/fixture-one").json()["asset"]["name"] == "Unchanged fixture"
            jobs = client.get("/api/v1/admin/jobs", headers={"X-Admin-Key": KEY})
            assert jobs.status_code == 200 and jobs.json()["mock"] is False

        recovered = request()
        assert recovered.status_code == (201 if kind == "feedback" else 200)
        assert recovered.json()["mock"] is False
        assert recovered.headers["X-Request-ID"] != identifier
        recovered_logs = [json.loads(record.getMessage()) for record in caplog.records
                          if record.name == "app.request" and record.getMessage().startswith("{")]
        recovered_summary, = [row for row in recovered_logs if row["request_id"] == recovered.headers["X-Request-ID"]]
        assert recovered_summary["error_code"] is None and recovered_summary["stage"] is None
        if kind != "feedback":
            assert recovered.json()["versions"] == VERSIONS
        assert counts(database) == (before[0] + (kind != "feedback"), before[1] + (kind == "feedback"))
        assert database.engine.pool.checkedout() == 0
