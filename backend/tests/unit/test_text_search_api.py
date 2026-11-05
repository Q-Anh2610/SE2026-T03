import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.export_openapi import contract_app
from app.main import create_app
from app.schemas.text_search import LiveTextSearchResponse
from app.services.text_search import SearchUnavailable


def test_service_mode_without_adapter_returns_503_before_opening_database():
    app = create_app(Settings(_env_file=None, env="production", text_search_source="service"))
    with TestClient(app) as client:
        response = client.post("/api/v1/search/text", json={"query": "chair"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SEARCH_UNAVAILABLE"
        assert app.state.db_engine is None
        assert "/api/v1/search/image" not in app.openapi()["paths"]


@pytest.mark.parametrize("body", [
    {"query": " "}, {"query": "x" * 501}, {"query": "chair", "page": True},
    {"query": "chair", "limit": "12"}, {"query": "chair", "filters": {"face_count_min": "1"}},
    {"query": "chair", "filters": {"face_count_min": 2, "face_count_max": 1}},
    {"query": "chair", "unknown": 1},
])
def test_invalid_input_is_400_even_when_service_and_database_are_unavailable(body):
    app = create_app(Settings(_env_file=None, env="test", text_search_source="service"))
    with TestClient(app) as client:
        response = client.post("/api/v1/search/text", json=body)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_REQUEST"
        assert app.state.db_engine is None


@pytest.mark.parametrize("error,status", [(SearchUnavailable("private-index-path"), 503),
                                          (RuntimeError("private-token"), 500)])
def test_adapter_errors_are_safe_no_database_and_service_is_reused_and_closed(error, status, caplog):
    class Service:
        calls = 0
        closed = False

        def search_text(self, query, filters, *, candidate_limit):
            self.calls += 1
            assert candidate_limit == 200
            raise error

        def close(self):
            self.closed = True

    service = Service()
    app = create_app(Settings(_env_file=None, env="test", text_search_source="service"), text_search_service=service)
    with TestClient(app) as client:
        for _ in range(2):
            response = client.post("/api/v1/search/text", json={"query": "sensitive query"})
            assert response.status_code == status
            assert not any(secret in response.text + caplog.text for secret in ("private-", "sensitive query", "Traceback"))
            assert app.state.db_engine is None
    assert service.calls == 2 and service.closed


def test_invalid_candidate_output_is_500_before_database_not_empty_success():
    class BadService:
        def search_text(self, *args, **kwargs):
            return {"hits": [], "versions": {}}
    app = create_app(Settings(_env_file=None, env="test", text_search_source="service"), text_search_service=BadService())
    with TestClient(app) as client:
        response = client.post("/api/v1/search/text", json={"query": "chair"})
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert app.state.db_engine is None


def test_service_openapi_is_exported_examples_validate_and_only_one_text_route():
    app = contract_app(text_search_source="service")
    schema = app.openapi()
    exported = Path(__file__).resolve().parents[3] / "docs/openapi-text-search.json"
    assert json.loads(exported.read_text(encoding="utf-8")) == schema
    operation = schema["paths"]["/api/v1/search/text"]["post"]
    assert "422" not in operation["responses"] and "503" in operation["responses"]
    LiveTextSearchResponse.model_validate(operation["responses"]["200"]["content"]["application/json"]["example"])
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/LiveTextSearchResponse")
    with TestClient(app) as client:
        assert client.post("/api/v1/search/text", json={"query": "chair"}).status_code == 503
    assert "[Mock]" in schema["paths"]["/api/v1/search/image"]["post"]["summary"]


def test_service_mode_always_uses_database_asset_routes_for_matching_detail_ids():
    app = create_app(Settings(_env_file=None, env="test", text_search_source="service", asset_list_source="fixture"))
    assert "[Mock]" not in app.openapi()["paths"]["/api/v1/assets/{asset_id}"]["get"]["summary"]
