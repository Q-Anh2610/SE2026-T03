"""PostgreSQL/concurrency thật; operation fixture, CLIP thật kiểm chứng riêng."""

from concurrent.futures import ThreadPoolExecutor
import os
from threading import Event
import time
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models import Job
from app.schemas.jobs import JobResult
from app.services.job_runner import Outcome
from app.services.reindex import ReindexFailure, RESOURCE
from scripts.asset_api_test_support import ROOT, isolated_asset_database

pytestmark = pytest.mark.integration
KEY = "fixture-admin-key-117-not-a-real-secret"
HEADERS = {"X-Admin-Key": KEY}


@pytest.fixture
def database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to isolated PostgreSQL test_* database.")
    with isolated_asset_database(value) as db:
        db.migrate()
        yield db


def application(db, tmp_path, operation):
    ready = tmp_path / "cache.json"
    ready.write_text("[]", encoding="utf-8")
    app = create_app(Settings(_env_file=None, env="test", admin_api_key=KEY, reindex_enabled=True,
        reindex_cache_ready=ready, reindex_output_root=tmp_path), reindex_operation=operation)
    app.state.db_engine = db.engine
    return app


def submit(client, request_id):
    return client.post("/api/v1/admin/reindex", headers=HEADERS, json={"request_id": str(request_id)})


def terminal(client, identifier):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        body = client.get(f"/api/v1/admin/jobs/{identifier}", headers=HEADERS).json()["job"]
        if body["status"] in ("succeeded", "failed"):
            return body
        time.sleep(.01)
    pytest.fail("Fixture worker did not finish in time.")


def success(*_):
    return Outcome(JobResult(input_count=200, succeeded=200, failed=0, skipped=0,
        index_version="fixture-index-117", asset_count=200, point_count=200, search_verified=True), processed=200, total=200)


def test_async_running_replay_conflict_completion_and_restart(database, tmp_path):
    release, started = Event(), Event()
    calls = []
    def operation(*args):
        calls.append(args[1])
        started.set()
        assert release.wait(5)
        return success()
    request_id = uuid4()
    app = application(database, tmp_path, operation)
    with TestClient(app) as client:
        try:
            response = submit(client, request_id)
            assert response.status_code == 202 and response.json()["reused"] is False
            identifier = response.json()["job_id"]
            assert started.wait(5)
            running = client.get(response.json()["status_url"], headers=HEADERS).json()["job"]
            assert running["status"] == "running" and running["progress"]["percent"] is None
            replay = submit(client, request_id)
            assert replay.status_code == 200 and replay.json()["job_id"] == identifier and replay.json()["reused"]
            assert submit(client, uuid4()).status_code == 409
        finally:
            release.set()
        finished = terminal(client, identifier)
        assert finished["status"] == "succeeded"
        assert finished["progress"]["percent"] == 100 and finished["result"]["point_count"] == 200
        assert len(calls) == 1
        assert submit(client, request_id).json()["job_id"] == identifier
        next_job = submit(client, uuid4())
        assert next_job.status_code == 202
        terminal(client, next_job.json()["job_id"])
    with TestClient(application(database, tmp_path, lambda *_: pytest.fail("Replay must not rerun"))) as restarted:
        replay = submit(restarted, request_id)
        assert replay.status_code == 200 and replay.json()["job_id"] == identifier


@pytest.mark.parametrize('fails', [False, True])
def test_concurrent_duplicate_requests_across_two_app_managers(database, tmp_path, fails):
    release = Event()
    calls = []
    def operation(*_):
        calls.append(True)
        assert release.wait(5)
        if fails:
            raise ReindexFailure('REINDEX_TIMEOUT')
        return success()
    with TestClient(application(database, tmp_path, operation)) as first, TestClient(application(database, tmp_path, operation)) as second:
        try:
            request_id = uuid4()
            with ThreadPoolExecutor(max_workers=4) as pool:
                responses = list(pool.map(lambda i: submit(first if i % 2 else second, request_id), range(4)))
            assert sorted(r.status_code for r in responses) == [200, 200, 200, 202]
            assert len({r.json()["job_id"] for r in responses}) == 1
            assert submit(second, uuid4()).status_code == 409
        finally:
            release.set()
        body = terminal(first, responses[0].json()["job_id"])
        assert body['status'] == ('failed' if fails else 'succeeded')
        assert submit(second, request_id).json()['job_id'] == body['job_id']
        assert len(calls) == 1


@pytest.mark.parametrize('outcome', [None, Outcome(JobResult(exit_code=2)), Outcome(JobResult(failed=1))])
def test_invalid_runner_output_is_durable_failed_and_replay_does_not_rerun(database, tmp_path, outcome):
    calls = []
    def operation(*_):
        calls.append(True)
        return outcome
    request_id = uuid4()
    with TestClient(application(database, tmp_path, operation)) as client:
        identifier = submit(client, request_id).json()['job_id']
        body = terminal(client, identifier)
        assert body['status'] == 'failed' and body['result'] is None
        assert body['error']['code'] == 'RUNNER_OUTPUT_INVALID'
        assert submit(client, request_id).json()['job_id'] == identifier
        assert len(calls) == 1
    with TestClient(application(database, tmp_path, lambda *_: pytest.fail('Replay must not execute'))) as restarted:
        assert submit(restarted, request_id).json()['status'] == 'failed'
    assert database.engine.pool.checkedout() == 0


@pytest.mark.parametrize('phase', ['start', 'failure'])
def test_state_commit_failure_preserves_guard_and_diagnoses_job(database, tmp_path, caplog, phase):
    import json
    calls = []
    def operation(*_):
        calls.append(True)
        raise ReindexFailure('REINDEX_OUTPUT_INVALID')
    rejected = 'running' if phase == 'start' else 'failed'
    # Literal allowlist fixture, chỉ trong schema UUID của test.
    with database.engine.begin() as connection:
        connection.exec_driver_sql(f"ALTER TABLE jobs ADD CONSTRAINT reject_phase CHECK (status <> '{rejected}') NOT VALID")
    app = application(database, tmp_path, operation)
    request_id = uuid4()
    with TestClient(app) as client:
        identifier = submit(client, request_id).json()['job_id']
        app.state.reindex_manager.close()
        body = client.get(f'/api/v1/admin/jobs/{identifier}', headers=HEADERS).json()['job']
        assert body['status'] == ('queued' if phase == 'start' else 'running')
        assert body['result'] is None and body['error'] is None
        assert len(calls) == (0 if phase == 'start' else 1)
        assert submit(client, request_id).json()['job_id'] == identifier
        assert submit(client, uuid4()).status_code == 409
        records = [json.loads(r.message) for r in caplog.records if r.name == 'app.services.reindex']
        assert records[-1]['stage'] == ('start_state' if phase == 'start' else 'failure_state')
        assert records[-1]['job_id'] == identifier
        assert records[-1]['error_code'] == 'JOB_STATE_UNAVAILABLE'
        if phase == 'failure':
            assert records[-1]['operation_error_code'] == 'REINDEX_OUTPUT_INVALID'
    assert database.engine.pool.checkedout() == 0


@pytest.mark.parametrize('reject', [None, 'running', 'failed'])
def test_scheduling_failure_never_runs_or_reports_success(database, tmp_path, caplog, reject):
    import json
    app = application(database, tmp_path, lambda *_: pytest.fail('Closed executor must not run'))
    request_id = uuid4()
    if reject:
        with database.engine.begin() as connection:
            connection.exec_driver_sql(f"ALTER TABLE jobs ADD CONSTRAINT reject_schedule CHECK (status <> '{reject}') NOT VALID")
    with TestClient(app, raise_server_exceptions=False) as client:
        # Khởi tạo manager bằng dependency như request thật, rồi đóng executor.
        from app.services.reindex import ReindexManager
        app.state.reindex_manager = ReindexManager(database.engine, app.state.settings,
            operation=lambda *_: pytest.fail('Closed executor must not run'))
        app.state.reindex_manager.close()
        response = submit(client, request_id)
        assert response.status_code == (503 if reject is None else 500)
        with Session(database.engine) as session:
            job = session.scalar(select(Job).where(Job.request_id == request_id))
            identifier, status = str(job.job_id), job.status
        assert status == {None: 'failed', 'running': 'queued', 'failed': 'running'}[reject]
        replay = submit(client, request_id)
        assert replay.status_code == 200 and replay.json()['job_id'] == identifier
        records = [json.loads(r.message) for r in caplog.records if r.name == 'app.services.reindex']
        assert records[0]['stage'] == 'scheduling' and records[0]['job_id'] == identifier
        assert records[0]['request_id'] == response.headers['X-Request-ID']
        if reject:
            assert records[-1]['operation_error_code'] == 'REINDEX_SCHEDULING_FAILED'
    assert database.engine.pool.checkedout() == 0


@pytest.mark.parametrize("error", [RuntimeError("private-password-or-path"), ReindexFailure("REINDEX_TIMEOUT")])
def test_runner_failure_is_durable_sanitized_and_releases_resource(database, tmp_path, error):
    def fail(*_):
        raise error
    app = application(database, tmp_path, fail)
    with TestClient(app) as client:
        identifier = submit(client, uuid4()).json()["job_id"]
        body = terminal(client, identifier)
        assert body["status"] == "failed" and "private" not in str(body)
        assert body["result"] is None
        app.state.reindex_manager.operation = success
        next_job = submit(client, uuid4())
        assert next_job.status_code == 202
        assert terminal(client, next_job.json()["job_id"])["status"] == "succeeded"


def test_database_rejection_prevents_worker_and_recovers(database, tmp_path):
    calls = []
    def operation(*_):
        calls.append(True)
        return success()
    with database.engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE jobs ADD CONSTRAINT reject_reindex CHECK (false) NOT VALID")
    with TestClient(application(database, tmp_path, operation), raise_server_exceptions=False) as client:
        try:
            response = submit(client, uuid4())
            assert response.status_code == 500 and calls == []
            with Session(database.engine) as session:
                assert session.scalar(select(func.count()).select_from(Job)) == 0
        finally:
            with database.engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE jobs DROP CONSTRAINT reject_reindex")
        accepted = submit(client, uuid4())
        assert terminal(client, accepted.json()["job_id"])["status"] == "succeeded"


def test_partial_unique_index_protects_resource_even_outside_api(database):
    with Session(database.engine) as session, session.begin():
        session.add(Job(kind="indexing", runner="fixture", status="queued", resource_key=RESOURCE))
    with pytest.raises(IntegrityError), Session(database.engine) as session, session.begin():
        session.add(Job(kind="indexing", runner="fixture", status="queued", resource_key=RESOURCE))


def test_0004_upgrade_preserves_old_job_and_drift_checks(database):
    with database.engine.begin() as connection:
        config = Config(str(ROOT / "backend/alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0003")
        identifier = uuid4()
        connection.execute(text("INSERT INTO jobs(job_id,kind,runner,status) VALUES (:id,'ingestion','legacy','queued')"), {"id": identifier})
        command.upgrade(config, "head")
        command.check(config)
        row = connection.execute(text("SELECT status,request_id,resource_key FROM jobs WHERE job_id=:id"), {"id": identifier}).one()
        assert tuple(row) == ("queued", None, None)


def test_final_commit_failure_never_claims_success(database, tmp_path, caplog):
    import json
    ran = Event()
    calls = []
    def operation(*_):
        calls.append(True)
        ran.set()
        return success()
    with database.engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE jobs ADD CONSTRAINT reject_final CHECK (status NOT IN ('succeeded','failed')) NOT VALID")
    app = application(database, tmp_path, operation)
    request_id = uuid4()
    with TestClient(app) as client:
        identifier = submit(client, request_id).json()["job_id"]
        assert ran.wait(5)
        app.state.reindex_manager.close()  # Chờ transaction cuối đã được thử.
        body = client.get(f"/api/v1/admin/jobs/{identifier}", headers=HEADERS).json()["job"]
        assert body["status"] == "running" and body["result"] is None
        assert submit(client, request_id).json()['job_id'] == identifier
        assert len(calls) == 1
        assert submit(client, uuid4()).status_code == 409
        records = [json.loads(r.message) for r in caplog.records if r.name == 'app.services.reindex']
        assert records[-1]['stage'] == 'final_state' and records[-1]['job_id'] == identifier
        assert records[-1]['intended_status'] == 'succeeded'
        assert records[-1]['error_code'] == 'JOB_STATE_UNAVAILABLE'
        with database.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE jobs DROP CONSTRAINT reject_final")
