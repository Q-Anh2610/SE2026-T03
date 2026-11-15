"""Quyền, request allowlist, readiness và contract của #117 trước khi mở DB."""

from uuid import uuid4
from pathlib import Path
from types import SimpleNamespace
import subprocess

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import create_app
from app.schemas.reindex import ReindexResponse
from app.services import reindex

KEY = "fixture-admin-key-117-not-a-real-secret"


def app():
    return create_app(Settings(_env_file=None, env="test", admin_api_key=KEY))


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Key": "wrong"}])
def test_denied_before_any_database(headers):
    with TestClient(app()) as client:
        response = client.post("/api/v1/admin/reindex", headers=headers, json={"request_id": str(uuid4())})
        assert response.status_code == 403
        assert client.app.state.db_engine is None


@pytest.mark.parametrize("payload", [
    {}, {"request_id": "invalid"}, {"request_id": str(uuid4()), "profile": "e5"},
    {"request_id": str(uuid4()), "snapshot": "arbitrary"},
    {"request_id": str(uuid4()), "manifest_path": "../../private"},
    {"request_id": str(uuid4()), "command": "arbitrary"},
])
def test_invalid_input_never_opens_database(payload):
    with TestClient(app()) as client:
        response = client.post("/api/v1/admin/reindex", headers={"X-Admin-Key": KEY}, json=payload)
        assert response.status_code == 400
        assert client.app.state.db_engine is None


def test_disabled_readiness_and_public_health():
    with TestClient(app()) as client:
        response = client.post("/api/v1/admin/reindex", headers={"X-Admin-Key": KEY}, json={"request_id": str(uuid4())})
        assert response.status_code == 503 and response.json()["error"]["code"] == "REINDEX_UNAVAILABLE"
        assert client.app.state.db_engine is None
        assert client.get("/healthz").status_code == 200


def test_openapi_has_admin_security_statuses_and_examples():
    operation = app().openapi()["paths"]["/api/v1/admin/reindex"]["post"]
    assert operation["security"] == [{"AdminKey": []}]
    assert {"200", "202", "400", "403", "409", "500", "503"} == operation["responses"].keys()
    for status in ("200", "202"):
        ReindexResponse.model_validate(operation["responses"][status]["content"]["application/json"]["example"])


@pytest.mark.parametrize("failure,code", [("timeout", "REINDEX_TIMEOUT"), ("exit", "INDEXING_FAILED"),
                                         ("output", "REINDEX_OUTPUT_INVALID")])
def test_child_failure_is_typed_and_uses_fixed_argv(monkeypatch, tmp_path, failure, code):
    ready = tmp_path / "ready.json"
    ready.write_text("[]", encoding="utf-8")
    settings = Settings(_env_file=None, reindex_enabled=True, reindex_cache_ready=ready, reindex_output_root=tmp_path)
    calls = []
    def execute(command, **kwargs):
        calls.append((command, kwargs))
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 10)
        return SimpleNamespace(returncode=1 if failure == "exit" else 0)
    monkeypatch.setattr(reindex.subprocess, "run", execute)
    identifier = uuid4()
    with pytest.raises(reindex.ReindexFailure) as error:
        reindex.run_index(settings, identifier)
    assert error.value.code == code
    assert Path(calls[0][0][1]).name == "prepare_text_search_index.py"
    assert calls[0][1].get("shell", False) is False
    assert calls[0][1]["timeout"] == settings.reindex_timeout_seconds
    assert "--cache-ready" in calls[0][0] and "--download-previews" not in calls[0][0]


def test_wrong_frozen_manifest_is_unavailable(monkeypatch, tmp_path):
    wrong = tmp_path / "wrong.json"
    wrong.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(reindex, "SOURCE", wrong)
    with pytest.raises(Exception) as error:
        reindex.validate_configuration(Settings(_env_file=None, reindex_enabled=True, reindex_cache_ready=wrong))
    assert error.value.status_code == 503
