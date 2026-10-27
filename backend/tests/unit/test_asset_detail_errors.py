from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.main import create_app


def test_detail_database_failure_is_sanitized_and_session_closed(monkeypatch, caplog):
    engine = MagicMock()
    session = MagicMock()
    session.get.side_effect = OperationalError("SELECT private_sql", {}, Exception("password=secret"))
    context = MagicMock()
    context.__enter__.return_value = session
    monkeypatch.setattr("app.db.dependencies.create_db_engine", lambda settings: engine)
    monkeypatch.setattr("app.db.dependencies.Session", lambda bind: context)
    with TestClient(create_app(Settings(_env_file=None, env="test"))) as client:
        response = client.get("/api/v1/assets/mock-chair-01")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in response.text + caplog.text
    assert "private_sql" not in response.text + caplog.text
    session.rollback.assert_called_once()
    context.__exit__.assert_called_once()
    engine.dispose.assert_called_once()


def test_oversized_asset_id_is_400_before_database_initialization(monkeypatch):
    def fail(settings):
        pytest.fail("Invalid ID must not initialize the database")
    monkeypatch.setattr("app.db.dependencies.create_db_engine", fail)
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get("/api/v1/assets/" + "a" * 129)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.parametrize("values", [
    {"env": "production", "asset_list_source": "fixture"},
    {"env": "test", "asset_list_source": "fixture", "mock_api_enabled": False},
])
def test_database_detail_available_when_mock_disabled(values):
    schema = create_app(Settings(_env_file=None, **values)).openapi()
    response = schema["paths"]["/api/v1/assets/{asset_id}"]["get"]
    assert response["summary"] == "Chi tiết asset từ PostgreSQL"
    assert response["responses"]["200"]["content"]["application/json"]["example"]["mock"] is False
    assert "/api/v1/search/text" not in schema["paths"]
