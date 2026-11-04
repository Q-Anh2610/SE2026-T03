"""PostgreSQL thật, schema test_* riêng; không gọi CLIP/Qdrant/Internet."""

import logging
import os

from fastapi import Depends
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.dependencies import get_db_session
from app.main import create_app
from app.models import Asset, SearchEvent
from app.schemas.text_search import LiveTextSearchRequest, SearchExecutionVersions
from app.services.search_events import persist_text_search_event
from scripts.asset_api_test_support import isolated_asset_database

pytestmark = pytest.mark.integration


@pytest.fixture
def event_database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL test_* database.")
    with isolated_asset_database(value) as database:
        database.migrate()
        yield database


def execution_versions():
    return SearchExecutionVersions(model_version="clip-test-revision", index_version="test-index-v1",
                                   config_version="test-top200-v1", dataset_snapshot="test-snapshot-sha256")


def test_event_is_committed_across_sessions_and_each_request_gets_new_uuid(event_database):
    engine = event_database.engine
    request = LiveTextSearchRequest(query="  ghế gỗ  ", filters={"license": "CC0", "face_count_min": 0})
    ids = []
    for page in (1, 2, 2):  # trang mới và retry đều tạo event riêng, kể cả trang rỗng.
        with Session(engine) as session:
            ids.append(persist_text_search_event(session, request.model_copy(update={"page": page}), execution_versions()))
    assert len(set(ids)) == 3
    with Session(engine) as reader:
        rows = list(reader.scalars(select(SearchEvent)))
        assert {r.search_event_id for r in rows} == set(ids)
        for row in rows:
            assert row.query_type == "text" and row.query_text == "ghế gỗ" and row.query_image_ref is None
            assert row.filters == {"license": "CC0", "face_count_min": 0}
            assert row.created_at is not None
            assert all(getattr(row, key) == value for key, value in execution_versions().model_dump().items())
    assert engine.pool.checkedout() == 0
    event_database.migrate()  # Alembic check: không đổi schema.


def test_invalid_versions_and_pending_writes_do_not_create_event(event_database):
    with Session(event_database.engine) as session:
        bad = execution_versions().model_copy(update={"model_version": "mock-w1"})
        with pytest.raises(ValidationError):
            persist_text_search_event(session, LiveTextSearchRequest(query="chair"), bad)
        assert session.scalar(select(func.count()).select_from(SearchEvent)) == 0
        session.add(Asset(asset_id="unrelated", source="test", source_id="unrelated"))
        with pytest.raises(ValueError, match="pending writes"):
            persist_text_search_event(session, LiveTextSearchRequest(query="chair"), execution_versions())
        session.rollback()


def test_db_failure_rolls_back_sanitizes_and_request_session_closes(event_database, monkeypatch, caplog):
    db = event_database
    logger = logging.getLogger("app.services.search_events")
    monkeypatch.setattr(logger, "handlers", [*logger.handlers, caplog.handler])
    caplog.set_level(logging.ERROR, logger=logger.name)
    app = create_app(Settings(_env_file=None, env="test", mock_api_enabled=False))
    app.state.db_engine = db.engine

    # Test-only route exercises actual request dependency/service/error handlers.
    # Product route remains mock until the next issue connects retrieval.
    @app.post("/test-only/events")
    def record(request: LiveTextSearchRequest, session: Session = Depends(get_db_session)):
        identifier = persist_text_search_event(session, request, execution_versions())
        return {"query_id": str(identifier), "search_event_id": str(identifier)}

    with TestClient(app) as client:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE search_events RENAME TO events_unavailable"))
        try:
            response = client.post("/test-only/events", json={"query": "private query"})
            assert response.status_code == 500
            assert response.json() == {"error": {"code": "INTERNAL_ERROR",
                "message": "Lỗi máy chủ. Vui lòng thử lại sau.", "details": []}}
            assert db.engine.pool.checkedout() == 0
            for secret in ("private query", "INSERT INTO", "events_unavailable", "Traceback", "postgresql+"):
                assert secret not in response.text + caplog.text
        finally:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE events_unavailable RENAME TO search_events"))
        invalid = client.post("/test-only/events", json={"query": " "})
        assert invalid.status_code == 400
        recovered = client.post("/test-only/events", json={"query": "chair"})
        assert recovered.status_code == 200
        assert recovered.json()["query_id"] == recovered.json()["search_event_id"]
        with Session(db.engine) as reader:
            assert reader.scalar(select(func.count()).select_from(SearchEvent)) == 1
        assert db.engine.pool.checkedout() == 0
    assert "Search event persistence failed" in caplog.text


def test_same_session_recovers_after_failed_commit(event_database):
    # Constraint lỗi thật ở PostgreSQL; service rollback trước khi caller tiếp tục.
    db = event_database
    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE search_events ADD CONSTRAINT test_reject_query CHECK (query_text <> 'reject')"))
    with Session(db.engine) as session:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as error:
            persist_text_search_event(session, LiveTextSearchRequest(query="reject"), execution_versions())
        assert error.value.status_code == 500 and session.is_active
        identifier = persist_text_search_event(session, LiveTextSearchRequest(query="accepted"), execution_versions())
    with Session(db.engine) as reader:
        assert reader.get(SearchEvent, identifier).query_text == "accepted"
        assert reader.scalar(select(func.count()).select_from(SearchEvent)) == 1
