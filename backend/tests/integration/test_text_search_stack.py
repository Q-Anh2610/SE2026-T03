"""HTTP + DB thật; retrieval fixture có nhãn rõ, không chạy encoder/Qdrant."""

import os

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models import Asset, SearchEvent
from app.schemas.text_search import TextSearchCandidates
from scripts.asset_api_test_support import isolated_asset_database

pytestmark = pytest.mark.integration
VERSIONS = dict(model_version="test-clip", index_version="test-index", config_version="test-top200",
                dataset_snapshot="test-fixture-snapshot")


class FixtureRetrieval:
    """Trả candidate cố định: chỉ kiểm chứng API contract/persistence."""
    def __init__(self, ids=("test-a", "test-b", "test-c")):
        self.ids = ids
        self.calls = []

    def search_text(self, query, filters, *, candidate_limit):
        self.calls.append((query, filters.model_dump(exclude_none=True), candidate_limit))
        return TextSearchCandidates(hits=[dict(asset_id=asset_id, score=.9 - i * .1)
                                         for i, asset_id in enumerate(self.ids)], versions=VERSIONS)


@pytest.fixture
def database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to isolated PostgreSQL test_* database.")
    with isolated_asset_database(value) as db:
        db.migrate()
        with Session(db.engine) as session, session.begin():
            for identifier in ("test-a", "test-b", "test-c"):
                session.add(Asset(asset_id=identifier, source="test-fixture", source_id=identifier,
                    name=None if identifier == "test-c" else identifier, category="Interior", license="CC0",
                    formats=["glb"], face_count=10, tags=[], thumbnail_path="C:/private/image.png",
                    source_url="https://example.org/" + identifier))
        yield db


def client_for(db, service):
    app = create_app(Settings(_env_file=None, env="test", debug=False, text_search_source="service"),
                     text_search_service=service)
    app.state.db_engine = db.engine
    return TestClient(app, raise_server_exceptions=False)


def event_count(db):
    with Session(db.engine) as session:
        return session.scalar(select(func.count()).select_from(SearchEvent))


def test_http_pagination_metadata_filters_and_committed_events(database):
    service = FixtureRetrieval()
    filters = dict(category="Interior", license="CC0", format="glb", face_count_min=10, face_count_max=10)
    identifiers = []
    with client_for(database, service) as client:
        for page in (1, 2, 2):
            response = client.post("/api/v1/search/text", json={"query": "  wooden chair  ", "filters": filters, "page": page, "limit": 2})
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["mock"] is False and body["versions"] == VERSIONS
            assert body["query"] == "wooden chair"
            assert body["query_id"] == body["search_event_id"]
            identifiers.append(body["search_event_id"])
            assert body["pagination"] == dict(page=page, limit=2, total=3, pages=2, has_next=page == 1)
            assert [item["rank"] for item in body["results"]] == ([1, 2] if page == 1 else [1])
            assert [item["asset"]["asset_id"] for item in body["results"]] == (["test-a", "test-b"] if page == 1 else ["test-c"])
            for result in body["results"]:
                assert result["asset"]["thumbnail_url"] is None
                assert client.get("/api/v1/assets/" + result["asset"]["asset_id"]).json()["asset"] == result["asset"]
            if page == 2:
                assert body["results"][0]["asset"]["name"] == "test-c"
            assert database.engine.pool.checkedout() == 0
        assert len(set(identifiers)) == 3
        assert service.calls == [("wooden chair", filters, 200)] * 3
        with Session(database.engine) as reader:
            events = list(reader.scalars(select(SearchEvent)))
            assert len(events) == 3
            for event in events:
                assert event.query_text == "wooden chair" and event.filters == filters
                assert all(getattr(event, key) == value for key, value in VERSIONS.items())


@pytest.mark.parametrize("ids,page,total,pages", [((), 1, 0, 0), (("test-a",), 99, 1, 1)])
def test_empty_or_out_of_range_success_still_creates_event(database, ids, page, total, pages):
    with client_for(database, FixtureRetrieval(ids)) as client:
        response = client.post("/api/v1/search/text", json={"query": "chair", "page": page})
        assert response.status_code == 200
        assert response.json()["results"] == []
        assert response.json()["pagination"] == dict(page=page, limit=12, total=total, pages=pages, has_next=False)
        assert event_count(database) == 1


def test_missing_candidate_outside_page_is_503_without_partial_results_or_event(database):
    with client_for(database, FixtureRetrieval(("test-a", "missing"))) as client:
        response = client.post("/api/v1/search/text", json={"query": "chair", "limit": 1})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SEARCH_UNAVAILABLE"
        assert event_count(database) == 0 and database.engine.pool.checkedout() == 0


def test_stale_filter_payload_is_503_not_silent_filtering(database):
    with client_for(database, FixtureRetrieval()) as client:
        response = client.post("/api/v1/search/text", json={"query": "chair", "filters": {"category": "Other"}})
        assert response.status_code == 503 and event_count(database) == 0


def test_event_commit_failure_is_safe_and_next_request_recovers(database):
    with database.engine.begin() as conn:
        conn.execute(text("ALTER TABLE search_events ADD CONSTRAINT test_event_failure CHECK (query_text <> 'reject')"))
    with client_for(database, FixtureRetrieval()) as client:
        response = client.post("/api/v1/search/text", json={"query": "reject"})
        assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert not any(secret in response.text for secret in ("reject", "INSERT", "test_event_failure", "postgresql", "Traceback"))
        assert event_count(database) == 0 and database.engine.pool.checkedout() == 0
        assert client.post("/api/v1/search/text", json={"query": "accepted"}).status_code == 200
        assert event_count(database) == 1


def test_invalid_mapping_is_rejected_before_event_commit(database):
    with database.engine.begin() as conn:
        conn.execute(text("UPDATE assets SET source = '' WHERE asset_id = 'test-a'"))
    with client_for(database, FixtureRetrieval()) as client:
        response = client.post("/api/v1/search/text", json={"query": "chair"})
        assert response.status_code == 500 and event_count(database) == 0


def test_database_read_failure_is_500_without_fixture_fallback(database):
    with database.engine.begin() as conn:
        conn.execute(text("ALTER TABLE assets RENAME TO test_assets_offline"))
    try:
        with client_for(database, FixtureRetrieval()) as client:
            response = client.post("/api/v1/search/text", json={"query": "chair"})
            assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
            assert event_count(database) == 0
    finally:
        with database.engine.begin() as conn:
            conn.execute(text("ALTER TABLE test_assets_offline RENAME TO assets"))
