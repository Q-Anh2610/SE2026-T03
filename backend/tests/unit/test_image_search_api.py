from io import BytesIO
from unittest.mock import Mock
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.core.config import Settings
from app.export_openapi import contract_app
from app.main import create_app
from app.schemas.image_search import LiveImageSearchResponse
from app.services.image_search_runtime import CLIPImageSearchAdapter
from app.services.text_search import SearchUnavailable
from app.search.image_search import SearchUnavailableError


def png():
    buffer = BytesIO()
    Image.new("RGB", (4, 4)).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.mark.parametrize("data,content", [
    ({"filters": "{"}, png()), ({"filters": '{"face_count_min":true}'}, png()),
    ({"filters": '{"extra":1}'}, png()), ({"page": "0"}, png()),
    ({"limit": "51"}, png()), ({}, b"broken"),
])
def test_invalid_upload_precedes_service_and_database(data, content):
    service = Mock()
    app = create_app(Settings(_env_file=None, env="test", image_search_source="service"), image_search_service=service)
    with TestClient(app) as client:
        response = client.post("/api/v1/search/image", files={"image": ("a.png", content)}, data=data)
        assert response.status_code == 400
        service.search_image.assert_not_called()
        assert app.state.db_engine is None


def test_unconfigured_image_service_503_and_production_route_present():
    app = create_app(Settings(_env_file=None, env="production", image_search_source="service"))
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.post("/api/v1/search/image").status_code == 400
        response = client.post("/api/v1/search/image", files={"image": ("a.png", png())})
        assert response.status_code == 503 and app.state.db_engine is None


def test_adapter_readiness_and_idempotent_close():
    service, client = Mock(), Mock()
    service.search_image.side_effect = SearchUnavailableError("secret")
    adapter = CLIPImageSearchAdapter(service, client)
    with pytest.raises(SearchUnavailable):
        adapter.search_image(png(), Mock())
    adapter.close()
    adapter.close()
    with pytest.raises(SearchUnavailable):
        adapter.search_image(png(), Mock())
    client.close.assert_called_once()
    assert service.search_image.call_count == 1


@pytest.mark.parametrize("failure", ["hash", "count", "processor", "model"])
def test_bootstrap_rejects_invalid_handoff_and_closes_client(monkeypatch, caplog, failure):
    from app.services import image_search_runtime as runtime
    import app.search.image_index_manifest as manifests

    manifest, client = Mock(), Mock()
    manifest.as_index_config.return_value = SimpleNamespace(
        model_id="wrong-model" if failure == "model" else "openai/clip-vit-base-patch32")
    manifest.point_count = 354
    client.count.return_value = SimpleNamespace(count=353 if failure == "count" else 354)
    if failure == "hash":
        manifest.verify_input_hashes.side_effect = ValueError("private-path")
    if failure == "processor":
        manifest.check_encoder.side_effect = ValueError("private-checkpoint")
    monkeypatch.setattr(manifests, "load_image_index_manifest", Mock(return_value=manifest))
    monkeypatch.setattr(runtime, "open_client", Mock(return_value=client))
    monkeypatch.setattr(runtime, "load_encoder", Mock(return_value=Mock()))
    settings = Settings(_env_file=None, image_index_manifest="manifest.json", image_index_root="input")
    assert runtime.build_image_search_service(settings) is None
    assert "private-" not in caplog.text
    if failure in {"hash", "model"}:
        runtime.open_client.assert_not_called()
    else:
        client.close.assert_called_once()


def test_live_openapi_image_contract():
    app = contract_app(text_search_source="service", image_search_source="service")
    schema = app.openapi()
    route = schema["paths"]["/api/v1/search/image"]["post"]
    assert "multipart/form-data" in route["requestBody"]["content"]
    assert set(route["responses"]) == {"200", "400", "500", "503"}
    LiveImageSearchResponse.model_validate(route["responses"]["200"]["content"]["application/json"]["example"])
    exported = Path(__file__).resolve().parents[3] / "docs/openapi-image-search.json"
    assert json.loads(exported.read_text(encoding="utf-8")) == schema
