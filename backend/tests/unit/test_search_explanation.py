"""Contract #116: nguồn/score đúng baseline, mock tách riêng, không nhận score fusion."""

from copy import deepcopy

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from io import BytesIO
from PIL import Image

from app.api.image_search import IMAGE_EXAMPLE
from app.api.text_search import EXAMPLE
from app.export_openapi import contract_app
from app.core.config import Settings
from app.main import create_app
from app.schemas.image_search import LiveImageSearchResponse
from app.schemas.text_search import LiveTextSearchResponse
from app.services.search_explanation import clip_explanation


@pytest.mark.parametrize("source,query_kind", [
    ("clip_text_to_preview", "văn bản truy vấn"),
    ("clip_image_to_preview", "ảnh truy vấn"),
])
def test_explanation_describes_comparison_and_score_semantics(source, query_kind):
    explanation = clip_explanation(source)
    assert query_kind in explanation and "ảnh preview" in explanation
    assert "cosine giảm dần" in explanation
    assert "không phải xác suất hay phần trăm chính xác" in explanation
    assert not any(term in explanation for term in ("mesh", "E5", "RRF", "SigLIP"))


@pytest.mark.parametrize("source", ["e5_text_to_metadata", "rrf", "mock_metadata", "unknown"])
def test_unknown_sources_do_not_receive_clip_explanation(source):
    with pytest.raises(ValueError):
        clip_explanation(source)


@pytest.mark.parametrize("model,example", [(LiveTextSearchResponse, EXAMPLE), (LiveImageSearchResponse, IMAGE_EXAMPLE)])
@pytest.mark.parametrize("score", [-1., -.125, 0., .25, 1.])
def test_live_scores_remain_raw_cosine_including_negative_and_zero(model, example, score):
    value = deepcopy(example)
    value["results"][0]["score"] = score
    result = model.model_validate(value).model_dump(mode="json")["results"][0]
    assert result["score"] == score and result["score_type"] == "cosine"


@pytest.mark.parametrize("change", ["score_type", "source", "nan", "range", "explanation"])
@pytest.mark.parametrize("model,example", [(LiveTextSearchResponse, EXAMPLE), (LiveImageSearchResponse, IMAGE_EXAMPLE)])
def test_live_result_rejects_wrong_score_semantics_or_source(model, example, change):
    value = deepcopy(example)
    result = value["results"][0]
    if change == "score_type": result["score_type"] = "rrf"
    elif change == "source": result["retrieval_sources"] = ["e5_text_to_metadata"]
    elif change == "nan": result["score"] = float("nan")
    elif change == "range": result["score"] = 25
    else: result["explanation"] = " "
    with pytest.raises(ValidationError):
        model.model_validate(value)


def test_mock_schema_does_not_claim_cosine_but_live_schema_documents_it():
    schema = contract_app(text_search_source="service").openapi()
    assert "score_type" not in schema["components"]["schemas"]["SearchResult"]["properties"]
    live = schema["components"]["schemas"]["LiveSearchResult"]["properties"]
    assert live["score_type"]["const"] == "cosine"
    assert (live["score"]["minimum"], live["score"]["maximum"]) == (-1, 1)


@pytest.mark.parametrize("kind", ["text", "image"])
def test_fusion_dto_is_rejected_before_db_instead_of_mislabeled_clip(kind):
    class FusionDTOService:
        def search_text(self, *args, **kwargs):
            return {"hits": [], "versions": EXAMPLE["versions"], "score_type": "rrf"}

        search_image = search_text

    service = FusionDTOService()
    app = create_app(Settings(_env_file=None, env="test", text_search_source="service", image_search_source="service"),
                     text_search_service=service, image_search_service=service)
    with TestClient(app, raise_server_exceptions=False) as client:
        if kind == "text":
            response = client.post("/api/v1/search/text", json={"query": "chair"})
        else:
            buffer = BytesIO()
            Image.new("RGB", (4, 4)).save(buffer, "PNG")
            response = client.post("/api/v1/search/image", files={"image": ("fixture.png", buffer.getvalue())})
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert app.state.db_engine is None
