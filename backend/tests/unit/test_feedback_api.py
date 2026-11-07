import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.export_openapi import contract_app
from app.main import create_app
from app.schemas.feedback import LiveFeedbackResponse


@pytest.mark.parametrize("payload", [
    {}, {"search_event_id": "mock-event", "asset_id": "one", "relevance": True},
    {"search_event_id": "00000000-0000-4000-8000-000000000081", "asset_id": "one", "relevance": 1},
    {"search_event_id": "00000000-0000-4000-8000-000000000081", "asset_id": "one", "relevance": "false"},
    {"search_event_id": "00000000-0000-4000-8000-000000000081", "asset_id": " ", "relevance": True},
    {"search_event_id": "00000000-0000-4000-8000-000000000081", "asset_id": "one", "relevance": True, "extra": "no"},
])
def test_validation_happens_before_opening_database(payload):
    app = create_app(Settings(_env_file=None, env="production", feedback_source="database"))
    with TestClient(app) as client:
        response = client.post("/api/v1/feedback", json=payload)
        assert response.status_code == 400 and response.json()["error"]["code"] == "INVALID_REQUEST"
        assert app.state.db_engine is None


def test_feedback_database_openapi_examples_and_export():
    schema = contract_app(text_search_source="service", image_search_source="service", feedback_source="database").openapi()
    operation = schema["paths"]["/api/v1/feedback"]["post"]
    assert set(operation["responses"]) == {"201", "400", "404", "500"}
    LiveFeedbackResponse.model_validate(operation["responses"]["201"]["content"]["application/json"]["example"])
    target = Path(__file__).resolve().parents[3] / "docs/openapi-feedback.json"
    assert json.loads(target.read_text(encoding="utf-8")) == schema
