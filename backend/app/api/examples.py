"""Ví dụ cố định để OpenAPI export tái lập được."""

from app.schemas.api import Versions
from app.services.mock_api import fixtures

ASSET_EXAMPLE = fixtures()[0].model_dump(mode="json")
PAGINATION_EXAMPLE = {"page": 1, "limit": 12, "total": 1, "pages": 1, "has_next": False}
SEARCH_EXAMPLE = {
    "query_id": "mock-query-example", "search_event_id": "mock-event-example",
    "query": "ghế gỗ", "results": [{
        "rank": 1, "asset": ASSET_EXAMPLE, "retrieval_sources": ["mock_metadata"],
        "explanation": "Minh họa khớp từ khóa metadata; chưa chạy semantic search.", "score": None,
    }], "versions": Versions().model_dump(), "pagination": PAGINATION_EXAMPLE, "mock": True,
}
IMAGE_SEARCH_EXAMPLE = {
    **SEARCH_EXAMPLE, "query": "mock-image:sha256-example",
    "results": [{**SEARCH_EXAMPLE["results"][0], "retrieval_sources": ["mock_preview_fixture"],
                 "explanation": "Kết quả mock cố định; chưa chạy image encoder."}],
}
FEEDBACK_EXAMPLE = {
    "feedback_id": "mock-feedback-example", "search_event_id": "mock-event-example",
    "asset_id": "mock-chair-01", "relevance": True,
    "created_at": "2026-10-19T00:00:00Z", "storage": "memory", "mock": True,
}


def response_example(value: dict) -> dict:
    return {"content": {"application/json": {"example": value}}}
