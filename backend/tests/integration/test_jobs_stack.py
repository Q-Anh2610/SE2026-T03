"""PostgreSQL/HTTP/lifecycle thật; tests ingestion dùng pipeline thật với preview cache fixture."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from uuid import uuid4

from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from PIL import Image
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models import Job
from app.schemas.jobs import JobResult
from app.services.job_runner import Outcome, execute_job, ingestion_operation
from app.services.jobs import create_job, finish_job, start_job
from scripts.asset_api_test_support import ROOT, isolated_asset_database

pytestmark = pytest.mark.integration
KEY = "fixture-admin-key-115-not-a-real-secret"
HEADERS = {"X-Admin-Key": KEY}


@pytest.fixture
def database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL test_* database.")
    with isolated_asset_database(value) as db:
        db.migrate()
        yield db


def application(database):
    app = create_app(Settings(_env_file=None, env="test", mock_api_enabled=False, admin_api_key=KEY))
    app.state.db_engine = database.engine
    return app


def test_empty_filters_pagination_and_stable_order(database):
    with TestClient(application(database)) as api:
        empty = api.get("/api/v1/admin/jobs", headers=HEADERS).json()
        assert empty["items"] == [] and empty["pagination"]["total"] == 0
        ids = [create_job(database.engine, kind=kind, runner="fixture")
               for kind in ("ingestion", "ingestion", "indexing")]
        start_job(database.engine, ids[0])
        finish_job(database.engine, ids[0], result={"input_count": 0}, processed=0, total=0)
        # Cùng timestamp để kiểm tra tie breaker UUID.
        with database.engine.begin() as connection:
            connection.execute(text("UPDATE jobs SET created_at=:t"), {"t": datetime(2000, 1, 1, tzinfo=timezone.utc)})
        first = api.get("/api/v1/admin/jobs?limit=2", headers=HEADERS).json()
        second = api.get("/api/v1/admin/jobs?limit=2&page=2", headers=HEADERS).json()
        assert [r["job_id"] for r in first["items"] + second["items"]] == sorted(map(str, ids), reverse=True)
        assert first["pagination"] == dict(page=1, limit=2, total=3, pages=2, has_next=True)
        filtered = api.get("/api/v1/admin/jobs?kind=ingestion&status=queued", headers=HEADERS).json()
        assert [r["job_id"] for r in filtered["items"]] == [str(ids[1])]
        huge = api.get("/api/v1/admin/jobs?page=" + "9" * 80, headers=HEADERS)
        assert huge.status_code == 200 and huge.json()["items"] == []
        detail = api.get(f"/api/v1/admin/jobs/{ids[0]}", headers=HEADERS).json()["job"]
        assert detail["progress"] == dict(unit="assets", processed=0, total=0, percent=None)
        missing = api.get(f"/api/v1/admin/jobs/{uuid4()}", headers=HEADERS)
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "JOB_NOT_FOUND"
        assert database.engine.pool.checkedout() == 0


def test_runner_commit_visibility_failure_sanitization_and_restart(database):
    observed = []
    def operation():
        with TestClient(application(database)) as reader:
            running = reader.get("/api/v1/admin/jobs?status=running", headers=HEADERS).json()["items"]
            assert len(running) == 1
            assert running[0]["started_at"] and running[0]["finished_at"] is None
            assert running[0]["progress"]["percent"] is None
            observed.append(running[0]["job_id"])
        raise RuntimeError("secret-database-url-or-file-path")
    identifier, success = execute_job(database.engine, kind="ingestion", runner="fixture", operation=operation)
    assert success is False
    assert observed == [str(identifier)]
    with TestClient(application(database)) as restarted:
        response = restarted.get(f"/api/v1/admin/jobs/{identifier}", headers=HEADERS)
        body = response.json()["job"]
        assert body["status"] == "failed" and body["finished_at"]
        assert body["error"]["code"] == "RUNNER_FAILED"
        assert "secret-database-url-or-file-path" not in response.text
        assert body["result"] is None
    with pytest.raises(ValueError):
        finish_job(database.engine, identifier)


def test_only_one_worker_can_start_same_job(database):
    identifier = create_job(database.engine, kind="indexing", runner="fixture")
    def start(_):
        try:
            start_job(database.engine, identifier)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(start, range(2))) == [False, True]


def test_failed_transition_rolls_back_and_api_recovers_after_database_error(database):
    identifier = create_job(database.engine, kind="ingestion", runner="fixture")
    start_job(database.engine, identifier)
    with pytest.raises(IntegrityError):
        finish_job(database.engine, identifier, processed=2, total=1)
    with Session(database.engine) as session:
        assert session.get(Job, identifier).status == "running"
    with TestClient(application(database), raise_server_exceptions=False) as api:
        with database.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE jobs RENAME TO jobs_temporarily_unavailable")
        try:
            response = api.get("/api/v1/admin/jobs", headers=HEADERS)
            assert response.status_code == 500
            assert response.json()["error"]["code"] == "INTERNAL_ERROR"
            assert "SELECT" not in response.text and "jobs_temporarily" not in response.text
        finally:
            with database.engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE jobs_temporarily_unavailable RENAME TO jobs")
        finish_job(database.engine, identifier, processed=1, total=1)
        assert api.get("/api/v1/admin/jobs", headers=HEADERS).status_code == 200
        assert database.engine.pool.checkedout() == 0


def test_no_operation_when_state_cannot_be_persisted(database):
    called = []
    with database.engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE jobs ADD CONSTRAINT reject_job CHECK (false) NOT VALID")
    try:
        with pytest.raises(SQLAlchemyError):
            execute_job(database.engine, kind="ingestion", runner="fixture",
                        operation=lambda: called.append(True))
        assert called == []
    finally:
        with database.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE jobs DROP CONSTRAINT reject_job")


@pytest.mark.parametrize('phase', ['start', 'final', 'failure'])
def test_cli_commit_fault_diagnostics_and_recovery(database, caplog, phase):
    calls = []
    def operation():
        calls.append(True)
        if phase == 'failure':
            raise RuntimeError('private-cli-diagnostic-fixture')
        return Outcome(JobResult(exit_code=0))
    rejected = 'running' if phase == 'start' else ('failed' if phase == 'failure' else 'succeeded')
    with database.engine.begin() as connection:
        connection.exec_driver_sql(f"ALTER TABLE jobs ADD CONSTRAINT reject_cli_phase CHECK (status <> '{rejected}') NOT VALID")
    try:
        with pytest.raises(SQLAlchemyError):
            execute_job(database.engine, kind='indexing', runner='fixture-cli', operation=operation)
        with Session(database.engine) as session:
            job = session.scalar(select(Job))
            assert job.status == ('queued' if phase == 'start' else 'running')
            assert job.result is None and job.error is None
            identifier = str(job.job_id)
        records = [json.loads(r.message) for r in caplog.records if r.name == 'app.services.job_runner']
        assert records[-1]['job_id'] == identifier
        assert records[-1]['stage'] == {'start': 'start_state', 'final': 'final_state', 'failure': 'failure_state'}[phase]
        assert len(calls) == (0 if phase == 'start' else 1)
        assert 'private-cli-diagnostic-fixture' not in caplog.text
    finally:
        with database.engine.begin() as connection:
            connection.exec_driver_sql('ALTER TABLE jobs DROP CONSTRAINT reject_cli_phase')
    _, succeeded = execute_job(database.engine, kind='indexing', runner='fixture-recovery',
        operation=lambda: Outcome(JobResult(exit_code=0)))
    assert succeeded and database.engine.pool.checkedout() == 0


@pytest.mark.parametrize("invalid_record", [False, True])
def test_actual_ingestion_pipeline_cached_preview_and_partial_failure(database, tmp_path, invalid_record):
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "blue").save(buffer, format="PNG")
    image = tmp_path / "preview.png"
    image.write_bytes(buffer.getvalue())
    digest = sha256(buffer.getvalue()).hexdigest()
    record = dict(asset_id="fixture-chair", source="objaverse", source_id="fixture-chair",
        source_url="https://sketchfab.com/3d-models/fixture-chair", name="Ghế fixture", license="CC0",
        thumbnail_path="https://media.sketchfab.com/models/fixture-chair/preview.png")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([record] + ([{"asset_id": "invalid"}] if invalid_record else [])), encoding="utf-8")
    previous = tmp_path / "previous.json"
    previous.write_text(json.dumps({"results": [{**record, "status": "downloaded",
        "preview_source_url": record["thumbnail_path"], "preview_local_path": str(image),
        "checksum": digest, "checksum_resource": "preview",
        "bytes": len(buffer.getvalue()), "width": 4, "height": 4}]}), encoding="utf-8")
    identifier, success = execute_job(database.engine, kind="ingestion", runner="ingestion.run_batch",
        operation=lambda: ingestion_operation(manifest_path=manifest, output_dir=tmp_path,
            report_path=tmp_path / "report.json", previous_report_path=previous))
    assert success is not invalid_record
    with TestClient(application(database)) as api:
        response = api.get(f"/api/v1/admin/jobs/{identifier}", headers=HEADERS)
        body = response.json()["job"]
        assert body["status"] == ("failed" if invalid_record else "succeeded")
        assert body["progress"]["processed"] == body["progress"]["total"] == 1 + int(invalid_record)
        assert body["progress"]["percent"] == 100
        assert body["result"]["skipped"] == 1
        assert body["result"]["failed"] == int(invalid_record)
        assert str(tmp_path) not in response.text
        report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert report["results"][-1]["status"] == "skipped"


def test_successful_index_job_keeps_unknown_progress(database):
    identifier, success = execute_job(database.engine, kind="indexing", runner="fixture-indexer",
        operation=lambda: Outcome(JobResult(exit_code=0)))
    assert success
    with TestClient(application(database)) as api:
        body = api.get(f"/api/v1/admin/jobs/{identifier}", headers=HEADERS).json()["job"]
        assert body["progress"] == dict(unit="assets", processed=None, total=None, percent=None)
        assert body["result"]["exit_code"] == 0


def test_upgrade_from_0002_preserves_asset_rows(database):
    # Chỉ thao tác schema UUID do fixture sở hữu, không hạ schema phát triển.
    with database.engine.begin() as connection:
        config = Config(str(ROOT / "backend/alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0002")
        connection.execute(text("INSERT INTO assets (asset_id, source, source_id, name) "
                                "VALUES ('legacy-115', 'fixture', 'legacy-115', 'Giữ nguyên tên')"))
        command.upgrade(config, "head")
        command.check(config)
        assert connection.scalar(text("SELECT name FROM assets WHERE asset_id='legacy-115'")) == "Giữ nguyên tên"
        assert connection.scalar(text("SELECT count(*) FROM jobs")) == 0
