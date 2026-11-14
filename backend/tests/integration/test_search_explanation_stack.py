"""#116: HTTP/PostgreSQL thật; retrieval fixture chỉ kiểm mapping, không đo chất lượng CLIP."""

from io import BytesIO
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
from app.services import text_search
from app.services.search_explanation import clip_explanation
from scripts.asset_api_test_support import isolated_asset_database

pytestmark = pytest.mark.integration
VERSIONS = dict(model_version="fixture-clip@fixture-revision", index_version="fixture-index-116",
                config_version="fixture-config-116", dataset_snapshot="fixture-snapshot-116")


class FixtureRetrieval:
    def __init__(self, hits):
        self.hits = hits

    def search_text(self, *args, **kwargs):
        return TextSearchCandidates(hits=self.hits, versions=VERSIONS)

    def search_image(self, *args, **kwargs):
        return self.search_text()


@pytest.fixture
def database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to isolated PostgreSQL test_* database.")
    with isolated_asset_database(value) as db:
        db.migrate()
        with Session(db.engine) as session, session.begin():
            session.add_all(Asset(asset_id=identifier, source="fixture", source_id=identifier,
                name=identifier, tags=[], formats=[]) for identifier in ("a", "b", "c"))
        yield db


def make_app(database, hits):
    service = FixtureRetrieval(hits)
    app = create_app(Settings(_env_file=None, env="test", mock_api_enabled=False,
        text_search_source="service", image_search_source="service"),
        text_search_service=service, image_search_service=service)
    app.state.db_engine = database.engine
    return app


def search(client, kind, **params):
    if kind == "text":
        return client.post("/api/v1/search/text", json={"query": "wooden chair", **params})
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, "PNG")
    return client.post("/api/v1/search/image", files={"image": ("fixture.png", buffer.getvalue())}, data=params)


def event_count(database):
    with Session(database.engine) as session:
        return session.scalar(select(func.count()).select_from(SearchEvent))


@pytest.mark.parametrize("kind", ["text", "image"])
def test_mapping_preserves_raw_scores_order_versions_pagination_and_events(database, kind):
    hits = [dict(asset_id="a", score=.25), dict(asset_id="b", score=0), dict(asset_id="c", score=-.125)]
    with TestClient(make_app(database, hits)) as client:
        for page in (1, 2):
            response = search(client, kind, page=page, limit=2)
            assert response.status_code == 200, response.text
            body = response.json()
            expected = hits[(page - 1) * 2:page * 2]
            assert body["versions"] == VERSIONS and body["mock"] is False
            assert [r["score"] for r in body["results"]] == [h["score"] for h in expected]
            assert [r["asset"]["asset_id"] for r in body["results"]] == [h["asset_id"] for h in expected]
            source = "clip_text_to_preview" if kind == "text" else "clip_image_to_preview"
            for result in body["results"]:
                assert result["score_type"] == "cosine"
                assert result["retrieval_sources"] == [source]
                assert result["explanation"] == clip_explanation(source)
            with Session(database.engine) as reader:
                event = reader.get(SearchEvent, UUID(body["search_event_id"]))
                assert event.query_type == kind
                assert event.result_asset_ids == [h["asset_id"] for h in expected]
                assert all(getattr(event, key) == value for key, value in VERSIONS.items())
        assert event_count(database) == 2


@pytest.mark.parametrize("kind", ["text", "image"])
@pytest.mark.parametrize("page,hits", [(1, []), (99, [dict(asset_id="a", score=.25)])])
def test_empty_results_keep_versions_and_never_invent_explanations(database, kind, page, hits):
    with TestClient(make_app(database, hits)) as client:
        response = search(client, kind, page=page)
        assert response.status_code == 200
        assert response.json()["results"] == [] and response.json()["versions"] == VERSIONS
        assert event_count(database) == 1


@pytest.mark.parametrize("kind", ["text", "image"])
@pytest.mark.parametrize("failure", ["empty", "unknown_source"])
def test_mapping_failure_does_not_commit_event_and_recovers(database, monkeypatch, kind, failure):
    original = text_search.clip_explanation
    with TestClient(make_app(database, [dict(asset_id="a", score=.25)]), raise_server_exceptions=False) as client:
        monkeypatch.setattr(text_search, "clip_explanation", lambda _: "" if failure == "empty" else clip_explanation("rrf"))
        response = search(client, kind)
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "Unsupported" not in response.text and event_count(database) == 0
        assert database.engine.pool.checkedout() == 0
        monkeypatch.setattr(text_search, "clip_explanation", original)
        assert search(client, kind).status_code == 200
        assert event_count(database) == 1
