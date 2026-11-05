from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import create_app
from app.schemas.text_search import TextSearchFilters
from app.search.text_search import SearchUnavailableError
from app.services.text_search import SearchUnavailable
from app.services import text_search_runtime as runtime


def test_adapter_maps_chi_readiness_error_and_closes_only_once():
    service = Mock()
    service.search_text.side_effect = SearchUnavailableError("private-index-reason")
    client = Mock()
    adapter = runtime.CLIPTextSearchAdapter(service, client)
    with pytest.raises(SearchUnavailable):
        adapter.search_text("chair", TextSearchFilters())
    adapter.close()
    adapter.close()
    client.close.assert_called_once()
    with pytest.raises(SearchUnavailable):
        adapter.search_text("chair", TextSearchFilters())
    assert service.search_text.call_count == 1


@pytest.mark.parametrize("case", ["hash", "count", "encoder"])
def test_failed_bootstrap_closes_resources_and_never_advertises_ready(monkeypatch, case, caplog):
    import app.search.index_manifest as module
    manifest = Mock()
    manifest.point_count = 2
    manifest.retrieval_config.candidate_limit = 200
    client = Mock()
    client.count.return_value = SimpleNamespace(count=1 if case == "count" else 2)
    if case == "hash":
        manifest.verify_input_hashes.side_effect = ValueError("private-local-path")
    if case == "encoder":
        manifest.check_encoder.side_effect = ValueError("private-model-path")
    monkeypatch.setattr(module, "load_index_manifest", Mock(return_value=manifest))
    monkeypatch.setattr(runtime, "open_client", Mock(return_value=client))
    monkeypatch.setattr(runtime, "load_encoder", Mock(return_value=Mock()))
    settings = Settings(_env_file=None, text_index_manifest="index.json", text_index_root="handoff")
    assert runtime.build_text_search_service(settings) is None
    assert "private-" not in caplog.text
    if case == "hash":
        runtime.open_client.assert_not_called()
    else:
        client.close.assert_called_once()


def test_open_client_never_creates_missing_local_storage(tmp_path):
    with pytest.raises(ValueError):
        runtime.open_client(Settings(_env_file=None, text_qdrant_local_path=tmp_path / "missing"))
    assert not (tmp_path / "missing").exists()


def test_missing_manifest_yields_safe_503_and_validation_still_wins(tmp_path):
    settings = Settings(_env_file=None, env="test", text_search_source="service",
                        text_index_manifest=tmp_path / "missing.json", text_index_root=tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.post("/api/v1/search/text", json={"query": " "}).status_code == 400
        assert client.post("/api/v1/search/text", json={"query": "chair"}).status_code == 503
        assert app.state.db_engine is None
