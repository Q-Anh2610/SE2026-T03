from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.api.mock import MAX_IMAGE_BYTES
from app.core.config import Settings
from app.main import create_app
from app.schemas.api import AssetFilters
from app.services.mock_api import matches


@pytest.fixture
def client():
    application = create_app(Settings(_env_file=None, env="test", debug=False, mock_api_enabled=True))
    with TestClient(application, raise_server_exceptions=False) as value:
        yield value


def image_bytes(format="PNG", size=(8, 8)):
    buffer = BytesIO()
    Image.new("RGB", size, color="white").save(buffer, format=format)
    return buffer.getvalue()


def test_asset_pagination_and_detail(client):
    result = client.get("/api/v1/assets", params={"page": 2, "limit": 2})
    assert result.status_code == 200
    body = result.json()
    assert len(body["items"]) == 2
    assert body["pagination"] == {"page": 2, "limit": 2, "total": 6, "pages": 3, "has_next": True}
    assert body["mock"] is True
    detail = client.get("/api/v1/assets/" + body["items"][0]["asset_id"])
    assert detail.json()["asset"] == body["items"][0]
    assert detail.json()["asset"]["license"] is None
    assert client.get("/api/v1/assets?page=99").json()["items"] == []


@pytest.mark.parametrize("filters,total", [
    ({"category": "Nội thất"}, 3), ({"category": "Nội thất", "format": "glb"}, 3),
    ({"format": "fbx"}, 0), ({"license": "CC0"}, 0),
    ({"face_count_min": 0}, 0), ({"face_count_max": 9999}, 0),
])
def test_filters_apply_before_pagination_and_do_not_invent_metadata(client, filters, total):
    response = client.get("/api/v1/assets", params={**filters, "limit": 1})
    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == total
    assert len(response.json()["items"]) == min(total, 1)


def test_face_count_inclusive_bounds_without_mutating_fixtures(client):
    asset = client.app.state.mock_store.assets[0].model_copy(update={"face_count": 10})
    assert matches(asset, AssetFilters(face_count_min=10, face_count_max=10))
    assert not matches(asset, AssetFilters(face_count_min=11))


@pytest.mark.parametrize("params", [{"page": 0}, {"limit": 51}, {"typo": "ignored?"},
                                       {"face_count_min": 5, "face_count_max": 1}])
def test_list_rejects_invalid_or_unknown_query_parameters(client, params):
    response = client.get("/api/v1/assets", params=params)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_text_search_preserves_frontend_shape_and_unicode_query(client):
    response = client.post("/api/v1/search/text", json={"query": "  GHE GO  ", "filters": {}, "limit": 12})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "GHE GO"
    assert body["query_id"].startswith("mock-") and body["search_event_id"].startswith("mock-")
    assert body["results"][0]["asset"]["asset_id"] == "mock-chair-01"
    assert body["results"][0]["rank"] == 1
    assert body["results"][0]["score"] is None
    assert body["versions"]["model_version"] == "mock-no-encoder"
    assert client.app.state.mock_store.events[body["search_event_id"]].query == "GHE GO"


def test_search_empty_and_pagination(client):
    empty = client.post("/api/v1/search/text", json={"query": "nonexistentfixture"})
    assert empty.status_code == 200
    assert empty.json()["results"] == []
    assert empty.json()["pagination"]["pages"] == 0
    result = client.post("/api/v1/search/text", json={"query": "gỗ", "page": 2, "limit": 1})
    assert result.status_code == 200
    assert result.json()["pagination"]["total"] == 3
    assert result.json()["results"][0]["asset"]["asset_id"] == "mock-table-01"
    assert result.json()["results"][0]["rank"] == 1


@pytest.mark.parametrize("body", [
    {"query": " "}, {"query": "a" * 501}, {"query": 123},
    {"query": "ghế", "limit": 0}, {"query": "ghế", "limit": True},
    {"query": "ghế", "limit": "12"}, {"query": "ghế", "page": 0},
    {"query": "ghế", "filters": {"unsupported": 1}},
    {"query": "ghế", "filters": {"face_count_min": True}},
    {"query": "ghế", "extra": "not accepted"},
])
def test_text_validation_is_400_with_standard_error(client, body):
    response = client.post("/api/v1/search/text", json=body)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_REQUEST" and error["details"]


def test_malformed_json_and_404_are_standard_errors(client):
    invalid = client.post("/api/v1/search/text", content="{broken", headers={"Content-Type": "application/json"})
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_REQUEST"
    missing = client.get("/api/v1/assets/missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ASSET_NOT_FOUND"
    assert client.get("/missing").json()["error"]["code"] == "HTTP_404"


@pytest.mark.parametrize("format", ["PNG", "JPEG"])
def test_image_search_decodes_file_content_and_returns_mock(client, format):
    response = client.post("/api/v1/search/image", files={"image": ("ignored.txt", image_bytes(format), "application/octet-stream")},
                           data={"filters": '{"category":"Nội thất"}', "limit": "2"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2 and body["pagination"]["total"] == 3
    assert body["query"].startswith("mock-image:")
    assert body["results"][0]["retrieval_sources"] == ["mock_preview_fixture"]
    assert body["versions"]["model_version"] == "mock-no-encoder"


@pytest.mark.parametrize("content,code", [
    (b"pretend PNG", "INVALID_IMAGE"),
    (image_bytes("GIF"), "UNSUPPORTED_IMAGE"),
    (image_bytes(size=(4097, 1)), "IMAGE_DIMENSIONS_EXCEEDED"),
    (b"a" * (MAX_IMAGE_BYTES + 1), "IMAGE_TOO_LARGE"),
], ids=["invalid-content", "unsupported-gif", "too-wide", "too-many-bytes"])
def test_image_validation(client, content, code):
    response = client.post("/api/v1/search/image", files={"image": ("preview.png", content, "image/png")})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


def test_image_missing_and_invalid_filter_json(client):
    assert client.post("/api/v1/search/image").status_code == 400
    response = client.post("/api/v1/search/image", files={"image": ("a.png", image_bytes())}, data={"filters": "{"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILTERS"


@pytest.mark.parametrize("relevance", [True, False])
def test_feedback_records_actual_search_association_in_memory(client, relevance):
    search = client.post("/api/v1/search/text", json={"query": "ghế gỗ"}).json()
    response = client.post("/api/v1/feedback", json={
        "search_event_id": search["search_event_id"], "asset_id": "mock-chair-01", "relevance": relevance,
    })
    assert response.status_code == 201
    body = response.json()
    assert body["storage"] == "memory" and body["mock"] is True
    assert body["relevance"] is relevance and body["created_at"]
    assert client.app.state.mock_store.feedbacks[-1].feedback_id == body["feedback_id"]


def test_feedback_rejects_unknown_event_mismatch_and_integer_relevance(client):
    request = {"search_event_id": "missing", "asset_id": "mock-chair-01", "relevance": True}
    assert client.post("/api/v1/feedback", json=request).status_code == 404
    request["search_event_id"] = client.post("/api/v1/search/text", json={"query": "ghế gỗ"}).json()["search_event_id"]
    request["asset_id"] = "mock-box-01"
    assert client.post("/api/v1/feedback", json=request).json()["error"]["code"] == "EVENT_ASSET_MISMATCH"
    request["relevance"] = 1
    assert client.post("/api/v1/feedback", json=request).status_code == 400


def test_mock_state_is_not_durable_between_app_instances(client):
    event_id = client.post("/api/v1/search/text", json={"query": "ghế"}).json()["search_event_id"]
    with TestClient(create_app(Settings(_env_file=None, env="test"))) as other:
        response = other.post("/api/v1/feedback", json={"search_event_id": event_id, "asset_id": "mock-chair-01", "relevance": True})
    assert response.status_code == 404


@pytest.mark.parametrize("values", [{"env": "production"}, {"env": "test", "mock_api_enabled": False}])
def test_mock_routes_are_disabled_outside_explicit_development_mode(values):
    with TestClient(create_app(Settings(_env_file=None, **values))) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/v1/assets").status_code == 404


def test_internal_error_does_not_expose_exception_message(client, monkeypatch):
    def fail(*args):
        raise RuntimeError("internal-secret-do-not-expose")
    monkeypatch.setattr(client.app.state.mock_store, "filtered", fail)
    response = client.get("/api/v1/assets")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "internal-secret" not in response.text


def test_local_frontend_cors_preflight(client):
    response = client.options("/api/v1/search/text", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
