from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_returns_ok():
    with TestClient(create_app(Settings(_env_file=None, env="test"))) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok"}


def test_health_is_get_only():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.post("/healthz")

    assert response.status_code == 405


def test_app_uses_environment_settings(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Configured API")
    monkeypatch.setenv("APP_DEBUG", "false")
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Configured API"
    assert "/healthz" in response.json()["paths"]
