"""HTTP/transactions PostgreSQL thật; retrieval fixture deterministic."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import os
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models import Asset, Feedback, SearchEvent
from app.schemas.text_search import TextSearchCandidates
from scripts.asset_api_test_support import ROOT, isolated_asset_database

pytestmark = pytest.mark.integration
VERSIONS = dict(model_version="fixture-clip", index_version="fixture-index",
                config_version="fixture-config", dataset_snapshot="fixture-snapshot")


class FixtureRetrieval:
    def result(self):
        return TextSearchCandidates(hits=[dict(asset_id="one", score=.9), dict(asset_id="two", score=.8)],
                                    versions=VERSIONS)

    def search_text(self, query, filters, *, candidate_limit):
        return self.result()

    def search_image(self, content, filters, *, candidate_limit):
        return self.result()


@pytest.fixture
def database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL test_* database.")
    with isolated_asset_database(value) as db:
        db.migrate()
        with Session(db.engine) as session, session.begin():
            for aid in ("one", "two", "other"):
                session.add(Asset(asset_id=aid, source="fixture", source_id=aid, name=aid, tags=[], formats=[]))
        yield db


def application(db):
    service = FixtureRetrieval()
    app = create_app(Settings(_env_file=None, env="test", mock_api_enabled=False,
        text_search_source="service", image_search_source="service", feedback_source="database"),
        text_search_service=service, image_search_service=service)
    app.state.db_engine = db.engine
    return app


def search(client, kind="text", **payload):
    if kind == "text":
        return client.post("/api/v1/search/text", json={"query": "chair", **payload})
    buffer = BytesIO()
    Image.new("RGB", (4, 4)).save(buffer, "PNG")
    return client.post("/api/v1/search/image", files={"image": ("a.png", buffer.getvalue())}, data=payload)


def feedback(client, event_id, asset_id="one", relevance=True):
    return client.post("/api/v1/feedback", json=dict(search_event_id=event_id, asset_id=asset_id, relevance=relevance))


def count(db):
    with Session(db.engine) as session:
        return session.scalar(select(func.count()).select_from(Feedback))


@pytest.mark.parametrize("kind", ["text", "image"])
def test_append_retry_change_rating_and_versions_durable_across_app_restart(database, kind):
    identifiers = []
    with TestClient(application(database)) as client:
        result = search(client, kind, limit=1)
        assert result.status_code == 200
        event_id = result.json()["search_event_id"]
        for rating in (True, True, False):
            response = feedback(client, event_id, relevance=rating)
            assert response.status_code == 201, response.text
            body = response.json()
            assert body["storage"] == "postgresql" and body["mock"] is False
            assert body["relevance"] is rating and body["search_event_id"] == event_id
            identifiers.append(body["feedback_id"])
            with Session(database.engine) as reader:
                saved = reader.get(Feedback, UUID(body["feedback_id"]))
                assert saved is not None and saved.relevance is rating
                assert saved.search_event.query_type == kind
                assert saved.search_event.result_asset_ids == ["one"]
                assert all(getattr(saved.search_event, key) == value for key, value in VERSIONS.items())
            assert database.engine.pool.checkedout() == 0
    assert len(set(identifiers)) == count(database) == 3
    with TestClient(application(database)) as restarted:
        assert feedback(restarted, event_id).status_code == 201
    assert count(database) == 4


def test_reject_off_page_and_other_assets_and_empty_events(database):
    with TestClient(application(database)) as client:
        page1 = search(client, page=1, limit=1).json()["search_event_id"]
        page2 = search(client, page=2, limit=1).json()["search_event_id"]
        empty = search(client, page=99).json()["search_event_id"]
        for event_id, asset_id in ((page1, "two"), (page2, "one"), (page1, "other"), (empty, "one")):
            response = feedback(client, event_id, asset_id)
            assert response.status_code == 400 and response.json()["error"]["code"] == "EVENT_ASSET_MISMATCH"
        assert count(database) == 0
        assert feedback(client, page2, "two").status_code == 201
        with Session(database.engine) as session:
            assert session.get(SearchEvent, UUID(empty)).result_asset_ids == []


def test_missing_ids_validation_and_legacy_snapshot_policy(database):
    with Session(database.engine) as session, session.begin():
        legacy = SearchEvent(query_type="text", query_text="old", **VERSIONS)
        session.add(legacy)
        session.flush()
        legacy_id = str(legacy.search_event_id)
    with TestClient(application(database)) as client:
        response = feedback(client, str(uuid4()))
        assert response.status_code == 404 and response.json()["error"]["code"] == "SEARCH_EVENT_NOT_FOUND"
        event_id = search(client).json()["search_event_id"]
        response = feedback(client, event_id, "missing")
        assert response.status_code == 404 and response.json()["error"]["code"] == "ASSET_NOT_FOUND"
        response = feedback(client, legacy_id)
        assert response.status_code == 400 and response.json()["error"]["code"] == "SEARCH_EVENT_RESULTS_UNAVAILABLE"
        assert count(database) == 0


def test_commit_failure_rolls_back_and_recovers(database):
    with TestClient(application(database), raise_server_exceptions=False) as client:
        event_id = search(client).json()["search_event_id"]
        with database.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE feedbacks ADD CONSTRAINT test_reject_feedback CHECK (false) NOT VALID")
        try:
            response = feedback(client, event_id)
            assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
            assert not any(s in response.text for s in ("INSERT", "postgresql", "test_reject_feedback", "Traceback"))
            assert count(database) == 0 and database.engine.pool.checkedout() == 0
        finally:
            with database.engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE feedbacks DROP CONSTRAINT test_reject_feedback")
        assert feedback(client, event_id).status_code == 201


def test_read_failure_is_safe_and_recovers(database):
    with TestClient(application(database), raise_server_exceptions=False) as client:
        event_id = search(client).json()["search_event_id"]
        with database.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE search_events RENAME TO test_events_offline")
        try:
            response = feedback(client, event_id)
            assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
            assert count(database) == 0 and database.engine.pool.checkedout() == 0
        finally:
            with database.engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE test_events_offline RENAME TO search_events")
        assert feedback(client, event_id).status_code == 201


def test_concurrent_repeated_feedback_keeps_all_rows(database):
    with TestClient(application(database)) as client:
        event_id = search(client).json()["search_event_id"]
        with ThreadPoolExecutor(max_workers=4) as executor:
            responses = list(executor.map(lambda _: feedback(client, event_id), range(4)))
        assert all(r.status_code == 201 for r in responses)
        assert len({r.json()["feedback_id"] for r in responses}) == count(database) == 4


def test_upgrade_0001_preserves_existing_rows_and_unknown_results(database):
    # Chỉ hạ/nâng schema tạm do fixture tạo, không tác động database phát triển.
    with database.engine.begin() as connection:
        config = Config(str(ROOT / "backend/alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0001")
        identifier = uuid4()
        connection.execute(text(
            "INSERT INTO search_events (search_event_id, query_type, query_text, model_version, index_version, config_version) "
            "VALUES (:id, 'text', 'legacy', 'old-model', 'old-index', 'old-config')"), {"id": identifier})
        connection.execute(text(
            "INSERT INTO feedbacks (feedback_id, search_event_id, asset_id, relevance) "
            "VALUES (:id, :event, 'one', true)"), {"id": uuid4(), "event": identifier})
        command.upgrade(config, "head")
        command.check(config)
        assert connection.scalar(text("SELECT result_asset_ids FROM search_events WHERE search_event_id=:id"),
                                 {"id": identifier}) is None
        assert connection.scalar(text("SELECT count(*) FROM feedbacks")) == 1
