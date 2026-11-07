"""HTTP và PostgreSQL thật với retrieval fixture; CLIP thật chạy smoke riêng."""

from hashlib import sha256
from io import BytesIO
import json
import os
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models import Asset, SearchEvent
from app.schemas.text_search import TextSearchCandidates
from app.search.image_search import InvalidQueryImageError
from app.services.text_search import SearchUnavailable
from scripts.asset_api_test_support import isolated_asset_database

pytestmark = pytest.mark.integration
VERSIONS = dict(model_version="test-clip", index_version="test-image-index",
                config_version="test-image-k200", dataset_snapshot="test-image-snapshot")


def png():
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, "PNG")
    return buffer.getvalue()


class FixtureImages:
    def __init__(self, ids=("image-a", "image-b", "image-c")):
        self.ids = ids
        self.error = None
        self.calls = []

    def search_image(self, content, filters, *, candidate_limit):
        self.calls.append((content, filters.model_dump(exclude_none=True), candidate_limit))
        if self.error is not None:
            raise self.error
        return TextSearchCandidates(
            hits=[dict(asset_id=aid, score=.9 - i * .1) for i, aid in enumerate(self.ids)], versions=VERSIONS)


@pytest.fixture
def database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL must point at an isolated PostgreSQL test_* database.")
    with isolated_asset_database(value) as db:
        db.migrate()
        with Session(db.engine) as session, session.begin():
            for aid in ("image-a", "image-b", "image-c"):
                session.add(Asset(asset_id=aid, source="test-fixture", source_id=aid,
                    name=aid, tags=[], formats=["glb"], face_count=10, category="Interior", license="CC0"))
        yield db


def client_for(db, service):
    app = create_app(Settings(_env_file=None, env="test", image_search_source="service",
        asset_list_source="fixture"), image_search_service=service)
    app.state.db_engine = db.engine
    return TestClient(app, raise_server_exceptions=False)


def upload(client, **data):
    return client.post("/api/v1/search/image", files={"image": ("name.txt", png(), "application/octet-stream")}, data=data)


def count_events(db):
    with Session(db.engine) as session:
        return session.scalar(select(func.count()).select_from(SearchEvent))


def test_pages_retry_details_and_image_events_committed(database):
    service = FixtureImages()
    filters = dict(category="Interior", license="CC0", format="glb", face_count_min=10, face_count_max=10)
    identifiers = []
    with client_for(database, service) as client:
        for page in (1, 2, 2):
            response = upload(client, page=page, limit=2, filters=json.dumps(filters))
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["mock"] is False and body["versions"] == VERSIONS
            assert body["query"] == "sha256:" + sha256(png()).hexdigest()
            assert body["search_event_id"] == body["query_id"]
            identifiers.append(body["search_event_id"])
            assert body["pagination"] == dict(page=page, limit=2, total=3, pages=2, has_next=page == 1)
            assert [r["asset"]["asset_id"] for r in body["results"]] == (["image-a", "image-b"] if page == 1 else ["image-c"])
            for result in body["results"]:
                assert result["retrieval_sources"] == ["clip_image_to_preview"]
                assert client.get("/api/v1/assets/" + result["asset"]["asset_id"]).json()["asset"] == result["asset"]
            with Session(database.engine) as reader:
                event = reader.get(SearchEvent, UUID(body["search_event_id"]))
                assert event.query_type == "image" and event.query_text is None
                assert event.query_image_ref == body["query"] and event.filters == filters
                assert all(getattr(event, key) == value for key, value in VERSIONS.items())
            assert database.engine.pool.checkedout() == 0
    assert len(set(identifiers)) == 3
    assert service.calls == [(png(), filters, 200)] * 3


@pytest.mark.parametrize("ids,page,total", [((), 1, 0), (("image-a",), 99, 1)])
def test_empty_and_out_of_range_still_persist(database, ids, page, total):
    with client_for(database, FixtureImages(ids)) as client:
        response = upload(client, page=page)
        assert response.status_code == 200 and response.json()["results"] == []
        assert response.json()["pagination"]["total"] == total
        assert count_events(database) == 1


@pytest.mark.parametrize("error,status,code", [
    (SearchUnavailable("private"), 503, "SEARCH_UNAVAILABLE"),
    (RuntimeError("private-password"), 500, "INTERNAL_ERROR"),
    (InvalidQueryImageError("INVALID_IMAGE"), 400, "INVALID_IMAGE"),
])
def test_retrieval_errors_are_safe_and_create_no_event(database, error, status, code):
    service = FixtureImages()
    service.error = error
    with client_for(database, service) as client:
        response = upload(client)
        assert response.status_code == status and response.json()["error"]["code"] == code
        assert "private" not in response.text and count_events(database) == 0
        service.error = None
        assert upload(client).status_code == 200 and count_events(database) == 1


def test_missing_off_page_or_stale_filter_candidate_is_503(database):
    service = FixtureImages(("image-a", "absent"))
    with client_for(database, service) as client:
        assert upload(client, limit=1).status_code == 503
        service.ids = ("image-a",)
        assert upload(client, filters='{"category":"Other"}').status_code == 503
        assert count_events(database) == 0


def test_db_write_failure_rollback_and_recovery(database):
    with database.engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE search_events ADD CONSTRAINT test_reject_image CHECK (query_type <> 'image')")
    with client_for(database, FixtureImages()) as client:
        response = upload(client)
        assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "test_reject_image" not in response.text
        assert count_events(database) == 0 and database.engine.pool.checkedout() == 0
        with database.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE search_events DROP CONSTRAINT test_reject_image")
        assert upload(client).status_code == 200 and count_events(database) == 1


def test_db_read_failure_is_safe(database):
    with database.engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE assets RENAME TO test_image_assets_offline")
    try:
        with client_for(database, FixtureImages()) as client:
            response = upload(client)
            assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
            assert count_events(database) == 0
    finally:
        with database.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE test_image_assets_offline RENAME TO assets")
