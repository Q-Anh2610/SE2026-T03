"""#118: các API W5 dùng chung app/DB; retrieval/reindex fixture, không phải smoke model."""

from io import BytesIO
import os
from threading import Event
import time
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models import Asset, Feedback, Job, SearchEvent
from app.schemas.jobs import JobResult
from app.schemas.text_search import TextSearchCandidates
from app.services.job_runner import Outcome
from app.services.jobs import finish_job
from scripts.asset_api_test_support import isolated_asset_database

pytestmark = pytest.mark.integration
KEY = "fixture-admin-key-118-not-a-real-secret"
HEADERS = {"X-Admin-Key": KEY}
VERSIONS = dict(model_version="fixture-clip@fixture-revision", index_version="fixture-active-index",
                config_version="fixture-active-config", dataset_snapshot="fixture-active-snapshot")


class FixtureRetrieval:
    def search_text(self, *_args, **_kwargs):
        return TextSearchCandidates(hits=[dict(asset_id="a", score=.5), dict(asset_id="b", score=-.1)], versions=VERSIONS)

    search_image = search_text


@pytest.fixture
def database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to isolated PostgreSQL test_* database.")
    with isolated_asset_database(value) as db:
        db.migrate()
        with Session(db.engine) as session, session.begin():
            session.add_all(Asset(asset_id=aid, source="fixture", source_id=aid, name=aid, tags=[], formats=[])
                            for aid in ("a", "b"))
        yield db


def application(db, tmp_path, operation):
    ready = tmp_path / "ready.json"
    ready.write_text("[]", encoding="utf-8")
    service = FixtureRetrieval()
    app = create_app(Settings(_env_file=None, env="test", mock_api_enabled=False,
        text_search_source="service", image_search_source="service", feedback_source="database",
        admin_api_key=KEY, reindex_enabled=True, reindex_cache_ready=ready),
        text_search_service=service, image_search_service=service, reindex_operation=operation)
    app.state.db_engine = db.engine
    return app


def search(client, kind):
    if kind == "text":
        return client.post("/api/v1/search/text", json={"query": "chair", "limit": 1})
    content = BytesIO()
    Image.new("RGB", (4, 4)).save(content, "PNG")
    return client.post("/api/v1/search/image", files={"image": ("fixture.png", content.getvalue())}, data={"limit": 1})


def feedback(client, body):
    return client.post("/api/v1/feedback", json={"search_event_id": body["search_event_id"],
        "asset_id": body["results"][0]["asset"]["asset_id"], "relevance": True})


def check_public_flow(client, db, kind):
    response = search(client, kind)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mock"] is False and body["versions"] == VERSIONS
    hit = body["results"][0]
    assert hit["score"] == .5 and hit["score_type"] == "cosine"
    assert hit["retrieval_sources"] == ["clip_text_to_preview" if kind == "text" else "clip_image_to_preview"]
    assert "không phải xác suất" in hit["explanation"]
    rated = feedback(client, body)
    assert rated.status_code == 201 and rated.json()["storage"] == "postgresql"
    with Session(db.engine) as reader:
        event = reader.get(SearchEvent, UUID(body["search_event_id"]))
        saved = reader.get(Feedback, UUID(rated.json()["feedback_id"]))
        assert event.query_type == kind and event.result_asset_ids == ["a"]
        assert saved.search_event_id == event.search_event_id
        assert all(getattr(event, field) == version for field, version in VERSIONS.items())
    return body


def wait_terminal(client, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/v1/admin/jobs/{job_id}", headers=HEADERS).json()["job"]
        if job["status"] in ("failed", "succeeded"):
            return job
        time.sleep(.01)
    pytest.fail("Fixture operation did not finish.")


@pytest.mark.parametrize("fails", [False, True])
def test_search_feedback_before_during_after_reindex_keep_active_versions(database, tmp_path, fails):
    release, started = Event(), Event()
    def operation(*_):
        started.set()
        assert release.wait(8)
        if fails:
            raise RuntimeError("private operation detail")
        return Outcome(JobResult(index_version="fixture-new-index", point_count=200,
                                 asset_count=200, succeeded=200, failed=0, search_verified=True), processed=200, total=200)
    app = application(database, tmp_path, operation)
    with TestClient(app) as client:
        for kind in ("text", "image"):
            check_public_flow(client, database, kind)
        request_id = str(uuid4())
        accepted = client.post("/api/v1/admin/reindex", headers=HEADERS, json={"request_id": request_id})
        assert accepted.status_code == 202 and started.wait(5)
        try:
            job_id = accepted.json()["job_id"]
            running = client.get(accepted.json()["status_url"], headers=HEADERS).json()["job"]
            assert running["status"] == "running"
            assert running["progress"]["percent"] is None
            for kind in ("text", "image"):
                check_public_flow(client, database, kind)
            replay = client.post("/api/v1/admin/reindex", headers=HEADERS, json={"request_id": request_id})
            assert replay.status_code == 200 and replay.json()["job_id"] == job_id
            assert client.post("/api/v1/admin/reindex", headers=HEADERS, json={"request_id": str(uuid4())}).status_code == 409
        finally:
            release.set()
        job = wait_terminal(client, job_id)
        assert job["status"] == ("failed" if fails else "succeeded")
        for kind in ("text", "image"):
            check_public_flow(client, database, kind)
        with Session(database.engine) as reader:
            assert reader.scalar(select(func.count()).select_from(SearchEvent)) == 6
            assert reader.scalar(select(func.count()).select_from(Feedback)) == 6
            assert reader.scalar(select(func.count()).select_from(Job)) == 1


def test_feedback_rollback_and_admin_denial_do_not_break_search_or_job_reads(database, tmp_path):
    with TestClient(application(database, tmp_path, lambda *_: pytest.fail("Unauthorized request must not run")),
                    raise_server_exceptions=False) as client:
        denied = client.post("/api/v1/admin/reindex", json={"request_id": str(uuid4())})
        assert denied.status_code == 403
        body = search(client, "text").json()
        with database.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE feedbacks ADD CONSTRAINT reject_feedback118 CHECK (false) NOT VALID")
        try:
            response = feedback(client, body)
            assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
            assert not any(value in response.text for value in ("INSERT", "reject_feedback118", "password"))
            assert search(client, "image").status_code == 200
            assert client.get("/api/v1/admin/jobs", headers=HEADERS).json()["items"] == []
            with Session(database.engine) as reader:
                assert reader.scalar(select(func.count()).select_from(Feedback)) == 0
        finally:
            with database.engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE feedbacks DROP CONSTRAINT reject_feedback118")
        assert feedback(client, body).status_code == 201
        assert database.engine.pool.checkedout() == 0


def test_final_job_commit_failure_does_not_rollback_independent_search_feedback(database, tmp_path):
    with database.engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE jobs ADD CONSTRAINT reject_final118 CHECK (status NOT IN ('succeeded','failed')) NOT VALID")
    app = application(database, tmp_path, lambda *_: Outcome(JobResult(exit_code=0)))
    with TestClient(app) as client:
        identifier = client.post("/api/v1/admin/reindex", headers=HEADERS, json={"request_id": str(uuid4())}).json()["job_id"]
        app.state.reindex_manager.close()
        try:
            job = client.get(f"/api/v1/admin/jobs/{identifier}", headers=HEADERS).json()["job"]
            assert job["status"] == "running" and job["result"] is None
            check_public_flow(client, database, "text")
            check_public_flow(client, database, "image")
        finally:
            with database.engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE jobs DROP CONSTRAINT reject_final118")
            finish_job(database.engine, UUID(identifier), error={"code": "FIXTURE_CLEANUP", "message": "Test-only cleanup."})
