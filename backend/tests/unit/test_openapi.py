import json
from pathlib import Path

from app.export_openapi import contract_app
from app.schemas.api import AssetDetailResponse, AssetListResponse, ErrorResponse, FeedbackResponse, SearchResponse


def test_export_matches_current_contract_and_all_schema_refs_resolve():
    schema = contract_app().openapi()
    exported = Path(__file__).resolve().parents[3] / "docs" / "openapi.json"
    assert json.loads(exported.read_text(encoding="utf-8")) == schema

    def check_refs(node):
        if isinstance(node, dict):
            if "$ref" in node:
                target = node["$ref"]
                assert target.startswith("#/components/schemas/")
                assert target.rsplit("/", 1)[1] in schema["components"]["schemas"]
            for value in node.values():
                check_refs(value)
        elif isinstance(node, list):
            for value in node:
                check_refs(value)
    check_refs(schema)


def test_all_mock_operations_have_valid_response_examples_and_standard_errors():
    schema = contract_app().openapi()
    operations = [
        ("/api/v1/assets", "get", "200", AssetListResponse),
        ("/api/v1/assets/{asset_id}", "get", "200", AssetDetailResponse),
        ("/api/v1/search/text", "post", "200", SearchResponse),
        ("/api/v1/search/image", "post", "200", SearchResponse),
        ("/api/v1/feedback", "post", "201", FeedbackResponse),
    ]
    for path, method, status, response_model in operations:
        responses = schema["paths"][path][method]["responses"]
        assert "422" not in responses
        response_model.model_validate(responses[status]["content"]["application/json"]["example"])
        for error in ("400", "404", "500"):
            ErrorResponse.model_validate(responses[error]["content"]["application/json"]["example"])
    image = schema["paths"]["/api/v1/search/image"]["post"]["requestBody"]["content"]
    assert "multipart/form-data" in image
