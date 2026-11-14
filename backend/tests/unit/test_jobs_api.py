"""Quyền quản trị, validation trước DB, contract OpenAPI và runner indexing."""

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.api.jobs import EXAMPLE
from app.core.config import Settings
from app.export_openapi import contract_app
from app.main import create_app
from app.schemas.jobs import JobDetailResponse, JobListResponse
from app.services import job_runner

KEY = "fixture-admin-key-115-not-a-real-secret"


def client(*, key=KEY):
    return TestClient(create_app(Settings(_env_file=None, env="test", admin_api_key=key)),
                      raise_server_exceptions=False)


@pytest.mark.parametrize("path", ["/api/v1/admin/jobs", "/api/v1/admin/jobs/not-a-uuid"])
def test_authentication_denies_before_database_access(path):
    with client() as api:
        for headers in ({}, {"X-Admin-Key": "wrong"}):
            response = api.get(path, headers=headers)
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "ADMIN_ACCESS_DENIED"
            assert api.app.state.db_engine is None


def test_unconfigured_admin_fails_closed_and_health_remains_public():
    with client(key=None) as api:
        response = api.get("/api/v1/admin/jobs", headers={"X-Admin-Key": KEY})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ADMIN_API_UNAVAILABLE"
        assert api.get("/healthz").json() == {"status": "ok"}
        assert api.app.state.db_engine is None


@pytest.mark.parametrize("path", [
    "/api/v1/admin/jobs?kind=bad", "/api/v1/admin/jobs?status=done",
    "/api/v1/admin/jobs?page=0", "/api/v1/admin/jobs?limit=51",
    "/api/v1/admin/jobs?unknown=value", "/api/v1/admin/jobs/not-a-uuid",
])
def test_validation_before_database(path):
    with client() as api:
        response = api.get(path, headers={"X-Admin-Key": KEY})
        assert response.status_code == 400, response.text
        assert response.json()["error"]["code"] == "INVALID_REQUEST"
        assert api.app.state.db_engine is None


def test_secret_constraints_and_repr():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, admin_api_key="short")
    assert KEY not in repr(Settings(_env_file=None, admin_api_key=KEY))


def test_admin_cors_preflight():
    with client() as api:
        response = api.options("/api/v1/admin/jobs", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Admin-Key",
        })
        assert response.status_code == 200
        assert "x-admin-key" in response.headers["access-control-allow-headers"].lower()


def test_jobs_examples_security_and_export():
    schema = contract_app().openapi()
    for path, model in (("/api/v1/admin/jobs", JobListResponse),
                        ("/api/v1/admin/jobs/{job_id}", JobDetailResponse)):
        operation = schema["paths"][path]["get"]
        assert operation["security"] == [{"AdminKey": []}]
        assert "422" not in operation["responses"]
        model.model_validate(operation["responses"]["200"]["content"]["application/json"]["example"])
        assert {"400", "403", "404", "500", "503"} <= operation["responses"].keys()
    assert schema["components"]["securitySchemes"]["AdminKey"]["name"] == "X-Admin-Key"
    assert JobDetailResponse(job=EXAMPLE).job.progress.percent == 100
    exported = Path(__file__).resolve().parents[3] / "docs/openapi.json"
    assert json.loads(exported.read_text(encoding="utf-8")) == schema


@pytest.mark.parametrize("exit_code", [0, 1])
def test_indexing_wrapper_uses_fixed_runner_and_unknown_progress(monkeypatch, tmp_path, exit_code):
    calls = []
    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=exit_code)
    monkeypatch.setattr(job_runner.subprocess, "run", fake_run)
    outcome = job_runner.indexing_operation(manifest_path=tmp_path / "manifest.json", snapshot="fixture")
    assert outcome.result.exit_code == exit_code
    assert (outcome.error is None) == (exit_code == 0)
    assert outcome.processed is None and outcome.total is None
    assert Path(calls[0][0][1]).name == "prepare_text_search_index.py"
    assert calls[0][1].get("shell", False) is False


def test_cli_requires_explicit_download_consent():
    with pytest.raises(SystemExit) as exc:
        job_runner.main(["indexing", "--manifest", "fixture.json", "--snapshot", "fixture"])
    assert exc.value.code == 2
