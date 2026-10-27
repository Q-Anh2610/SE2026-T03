from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.main import create_app
from app.services.assets import public_thumbnail


@pytest.mark.parametrize("value", [None, "", "/private/a.png", r"C:\private\a.png",
                                   "file:///private/a.png", "javascript:alert(1)",
                                   "https://user:secret@example.org/a.png", "https://[invalid"])
def test_thumbnail_does_not_expose_local_paths_or_credentials(value):
    assert public_thumbnail(value) is None


def test_missing_db_config_is_safe_and_never_uses_mock(monkeypatch, caplog):
    for key in ("DATABASE_URL", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    application = create_app(Settings(_env_file=None, env="test", asset_list_source="database"))
    with TestClient(application) as client:
        assert client.get("/healthz").status_code == 200
        response = client.get("/api/v1/assets")
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL_ERROR", "message": "Lỗi máy chủ. Vui lòng thử lại sau.", "details": []}}
    assert "mock-chair" not in response.text
    assert "database request failed" in caplog.text


def test_db_failure_rolls_back_closes_session_and_disposes_engine(monkeypatch, caplog):
    engine = MagicMock()
    session = MagicMock()
    session.scalar.side_effect = OperationalError("SELECT secret", {}, Exception("password=secret"))
    context = MagicMock()
    context.__enter__.return_value = session
    monkeypatch.setattr("app.db.dependencies.create_db_engine", lambda settings: engine)
    monkeypatch.setattr("app.db.dependencies.Session", lambda bind: context)
    application = create_app(Settings(_env_file=None, env="test"))
    with TestClient(application) as client:
        response = client.get("/api/v1/assets")
        assert response.status_code == 500
        assert "secret" not in response.text and "secret" not in caplog.text
        assert "mock" not in response.json()
    session.rollback.assert_called_once()
    context.__exit__.assert_called_once()
    engine.dispose.assert_called_once()


def test_invalid_query_is_rejected_before_database_initialization(monkeypatch):
    def fail(settings):
        pytest.fail("Invalid query must not initialize the database")
    monkeypatch.setattr("app.db.dependencies.create_db_engine", fail)
    with TestClient(create_app(Settings(_env_file=None))) as client:
        for query in ("page=0", "limit=51", "face_count_min=20&face_count_max=10", "typo=value"):
            response = client.get("/api/v1/assets?" + query)
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.parametrize("settings", [
    {"env": "production", "asset_list_source": "fixture"},
    {"env": "test", "mock_api_enabled": False, "asset_list_source": "fixture"},
])
def test_fixture_selection_cannot_enable_mock_in_production_or_when_disabled(settings):
    application = create_app(Settings(_env_file=None, **settings))
    operation = application.openapi()["paths"]["/api/v1/assets"]["get"]
    assert operation["summary"] == "Danh sách asset từ PostgreSQL"
    assert "/api/v1/search/text" not in application.openapi()["paths"]
