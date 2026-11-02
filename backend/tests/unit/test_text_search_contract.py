from copy import deepcopy
from uuid import uuid4
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.text_search import (
    LiveTextSearchRequest, LiveTextSearchResponse, SearchExecutionVersions,
    TextSearchCandidates,
)
from app.export_text_search_contract import contract_schema


def versions():
    # Version labels tự tạo: kiểm thử contract, không phải bằng chứng retrieval thật.
    return dict(model_version="clip-test-revision", index_version="test-index-v1",
                config_version="test-top200-v1", dataset_snapshot="test-snapshot-sha256")


@pytest.mark.parametrize("value", [True, 1.0, "1", -1])
def test_live_json_face_count_requires_nonnegative_integer(value):
    with pytest.raises(ValidationError):
        LiveTextSearchRequest(query="chair", filters={"face_count_min": value})


def test_request_normalizes_query_and_filters_and_rejects_invalid_range():
    request = LiveTextSearchRequest(query="  ghế gỗ  ", filters={"category": " Nội thất "})
    assert request.query == "ghế gỗ" and request.page == 1 and request.limit == 12
    assert request.filters.model_dump(exclude_none=True) == {"category": "Nội thất"}
    for changes in ({"query": " "}, {"query": "x" * 501}, {"page": True}, {"limit": "12"},
                    {"filters": {"face_count_min": 3, "face_count_max": 2}}, {"filters": {"unknown": 1}}):
        with pytest.raises(ValidationError):
            LiveTextSearchRequest.model_validate({"query": "chair", **changes})


@pytest.mark.parametrize("field", list(versions()))
@pytest.mark.parametrize("value", ["", " ", "mock-w1", "MOCK-index"])
def test_execution_versions_are_explicit_and_never_mock(field, value):
    with pytest.raises(ValidationError):
        SearchExecutionVersions(**{**versions(), field: value})


@pytest.mark.parametrize("hits", [
    [{"asset_id": "a", "score": .3}, {"asset_id": "a", "score": .2}],
    [{"asset_id": "a", "score": .2}, {"asset_id": "b", "score": .3}],
    [{"asset_id": "b", "score": .3}, {"asset_id": "a", "score": .3}],
    [{"asset_id": "a/b", "score": .3}], [{"asset_id": "a", "score": float("nan")}],
    [{"asset_id": str(i), "score": .3} for i in range(201)],
])
def test_candidates_reject_duplicates_wrong_order_invalid_ids_scores_and_cap(hits):
    with pytest.raises(ValidationError):
        TextSearchCandidates(hits=hits, versions=versions())


def response_payload():
    identifier = str(uuid4())
    asset = dict(asset_id="a", name="Chair", source="test", description=None, category=None,
                 tags=[], formats=[], face_count=None, thumbnail_url=None, source_url=None,
                 author=None, license=None)
    return dict(query_id=identifier, search_event_id=identifier, query="chair", mock=False,
                versions=versions(), pagination=dict(page=1, limit=12, total=1, pages=1, has_next=False),
                results=[dict(rank=1, asset=asset, score=-.1,
                              retrieval_sources=["clip_text_to_preview"], explanation="CLIP cosine similarity.")])


def test_live_response_accepts_negative_cosine_and_requires_explicit_false():
    payload = response_payload()
    assert LiveTextSearchResponse.model_validate(payload).results[0].score == -.1
    for value in [True, None, 0, "false"]:
        with pytest.raises(ValidationError):
            LiveTextSearchResponse.model_validate({**payload, "mock": value})
    del payload["mock"]
    with pytest.raises(ValidationError):
        LiveTextSearchResponse.model_validate(payload)


@pytest.mark.parametrize("change", ["id", "rank", "count", "pages", "total", "url", "source", "score"])
def test_response_rejects_mapping_and_pagination_contract_violations(change):
    p = deepcopy(response_payload())
    if change == "id": p["query_id"] = str(uuid4())
    if change == "rank": p["results"][0]["rank"] = 2
    if change == "count": p["results"] = []
    if change == "pages": p["pagination"]["pages"] = 2
    if change == "total": p["pagination"]["total"] = 201
    if change == "url": p["results"][0]["asset"]["source_url"] = "https://user:secret@example.org/x"
    if change == "source": p["results"][0]["retrieval_sources"] = ["mock_metadata"]
    if change == "score": p["results"][0]["score"] = None
    with pytest.raises(ValidationError):
        LiveTextSearchResponse.model_validate(p)


def test_empty_and_out_of_range_pages_are_successful_responses():
    for total, page, pages in [(0, 1, 0), (1, 2, 1)]:
        p = response_payload()
        p.update(results=[], pagination=dict(page=page, limit=12, total=total, pages=pages, has_next=False))
        assert LiveTextSearchResponse.model_validate(p).results == []


def test_exported_contract_matches_models_and_all_refs_resolve():
    schema = contract_schema()
    saved = Path(__file__).resolve().parents[3] / "docs/contracts/text-search-w3.schema.json"
    assert json.loads(saved.read_text(encoding="utf-8")) == schema

    def visit(value):
        if isinstance(value, dict):
            if "$ref" in value:
                assert value["$ref"].startswith("#/$defs/")
                assert value["$ref"].split("/")[-1] in schema["$defs"]
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(schema)
