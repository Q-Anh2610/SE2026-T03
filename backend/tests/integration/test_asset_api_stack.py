"""Migration → ingestion/seed → session thật → API; dữ liệu test, không gọi Internet."""

from io import BytesIO
import json
import logging
import os
from unittest.mock import Mock

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.seed import seed_assets
from app.ingestion.db_writer import DatabaseWriter
from app.ingestion.pipeline import run_batch
from app.main import create_app
from app.models import Asset
from scripts.asset_api_test_support import isolated_asset_database

pytestmark = pytest.mark.integration


@pytest.fixture
def stack_database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL test_* database.")
    with isolated_asset_database(value) as database:
        yield database


def api_client(database):
    application = create_app(Settings(_env_file=None, env="test", debug=False, asset_list_source="database"))
    # Chỉ cấp engine của schema test. Không override session, service hay router.
    application.state.db_engine = database.engine
    return TestClient(application)


def test_empty_schema_migration_seed_and_api_stack(stack_database):
    database = stack_database
    assert inspect(database.engine).get_table_names() == []
    database.migrate()
    with Session(database.engine) as session, session.begin():
        assert seed_assets(session) == 7
    with Session(database.engine) as session, session.begin():
        assert seed_assets(session) == 0
    with api_client(database) as client:
        listing = client.get("/api/v1/assets?page=2&limit=2&category=Nội thất")
        assert listing.status_code == 200
        body = listing.json()
        assert body["mock"] is False and len(body["items"]) == 2
        assert body["pagination"] == {"page": 2, "limit": 2, "total": 7, "pages": 4, "has_next": True}
        for asset in body["items"]:
            detail = client.get("/api/v1/assets/" + asset["asset_id"])
            assert detail.json() == {"asset": asset, "mock": False}
        assert database.engine.pool.checkedout() == 0
    with database.engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
    database.migrate()  # Schema check vẫn đạt sau seed và request API.


def test_real_database_failure_is_safe_and_next_request_recovers(stack_database, caplog, monkeypatch):
    database = stack_database
    database.migrate()
    # Alembic fileConfig thay root handlers; gắn capture vào đúng logger cần đo.
    logger = logging.getLogger("app.db.dependencies")
    monkeypatch.setattr(logger, "handlers", [*logger.handlers, caplog.handler])
    caplog.set_level(logging.ERROR, logger="app.db.dependencies")
    with api_client(database) as client:
        for path in ("/api/v1/assets?limit=0", "/api/v1/assets/" + "x" * 129):
            response = client.get(path)
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "INVALID_REQUEST"
        missing = client.get("/api/v1/assets/mock-chair-01")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "ASSET_NOT_FOUND"
        with database.engine.begin() as connection:
            connection.execute(text("ALTER TABLE assets RENAME TO assets_temporarily_unavailable"))
        try:
            for path in ("/api/v1/assets", "/api/v1/assets/mock-chair-01"):
                response = client.get(path)
                assert response.status_code == 500
                assert response.json() == {"error": {
                    "code": "INTERNAL_ERROR", "message": "Lỗi máy chủ. Vui lòng thử lại sau.", "details": [],
                }}
                assert database.engine.pool.checkedout() == 0
                assert not any(value in response.text + caplog.text for value in (
                    "SELECT ", "Traceback", "assets_temporarily_unavailable", "postgresql://", "postgresql+psycopg://",
                ))
        finally:
            with database.engine.begin() as connection:
                connection.execute(text("ALTER TABLE assets_temporarily_unavailable RENAME TO assets"))
        assert client.get("/api/v1/assets").json()["items"] == []
        assert client.get("/healthz").json() == {"status": "ok"}
    assert "Asset database request failed" in caplog.text


def test_ingestion_pipeline_rerun_is_visible_through_api(stack_database, tmp_path, monkeypatch):
    database = stack_database
    database.migrate()
    # Ảnh và metadata tự tạo; chỉ transport HTTP là giả, pipeline/decode/DB/API thật.
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    content = buffer.getvalue()
    calls = []

    def open_preview(url, timeout):
        calls.append(url)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.geturl.return_value = url
        response.read.return_value = content
        return response

    monkeypatch.setattr("app.ingestion.downloader.urlopen", open_preview)
    assets = [dict(asset_id=f"fixture-ingested-{i}", source="fixture", source_id=str(i),
                   source_url=f"https://example.org/fixture/{i}", license="fixture-only",
                   name=f"Pipeline fixture {i}", category="pipeline-fixture", formats=["glb"],
                   thumbnail_path=f"https://media.sketchfab.com/models/fixture-{i}/preview.png")
              for i in (1, 2)]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(assets), encoding="utf-8")
    writer = DatabaseWriter()
    writer.engine = database.engine  # Không mở kết nối tới database phát triển.
    first = tmp_path / "first.json"
    report = run_batch(manifest, tmp_path / "previews", first, max_attempts=1, persist_asset=writer)
    assert report["summary"] == {"input_count": 2, "succeeded": 2, "failed": 0, "skipped": 0}
    rerun = run_batch(manifest, tmp_path / "previews", tmp_path / "second.json",
                      previous_report_path=first, max_attempts=1, persist_asset=writer)
    assert rerun["summary"] == {"input_count": 2, "succeeded": 0, "failed": 0, "skipped": 2}
    assert len(calls) == 2
    assert all(item["database_status"] == "saved" for item in rerun["results"])
    with api_client(database) as client:
        body = client.get("/api/v1/assets?category=pipeline-fixture&format=glb&limit=1&page=2").json()
        assert body["mock"] is False and body["pagination"]["total"] == 2
        asset = body["items"][0]
        assert asset["source"] == "fixture"
        assert client.get("/api/v1/assets/" + asset["asset_id"]).json()["asset"] == asset
    with Session(database.engine) as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 2
        assert {asset.ingestion_status for asset in session.scalars(select(Asset))} == {"downloaded"}
        assert all(asset.index_version is None for asset in session.scalars(select(Asset)))
