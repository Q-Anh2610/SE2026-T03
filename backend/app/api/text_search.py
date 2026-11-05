"""Route #65: service → metadata DB → pagination → durable event."""

import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.examples import ASSET_EXAMPLE, PAGINATION_EXAMPLE, response_example
from app.core.errors import api_error
from app.db.dependencies import get_db_session
from app.schemas.api import ErrorResponse
from app.schemas.text_search import LiveTextSearchRequest, LiveTextSearchResponse, TEXT_CANDIDATE_LIMIT, TextSearchCandidates
from app.services.text_search import SearchUnavailable, execute_text_search, unavailable

logger = logging.getLogger(__name__)

ERRORS = {
    status: {"model": ErrorResponse, **response_example({"error": {"code": code, "message": message, "details": []}})}
    for status, code, message in [
        (400, "INVALID_REQUEST", "Yêu cầu không hợp lệ."),
        (500, "INTERNAL_ERROR", "Lỗi máy chủ. Vui lòng thử lại sau."),
        (503, "SEARCH_UNAVAILABLE", "Dịch vụ tìm kiếm chưa sẵn sàng. Vui lòng thử lại sau."),
    ]
}
EXAMPLE = {
    "query_id": "00000000-0000-4000-8000-000000000065",
    "search_event_id": "00000000-0000-4000-8000-000000000065",
    "query": "wooden chair", "mock": False,
    "versions": {"model_version": "example-clip-revision", "index_version": "example-index",
                 "config_version": "example-top200", "dataset_snapshot": "example-snapshot"},
    "pagination": PAGINATION_EXAMPLE,
    "results": [{"rank": 1, "asset": {**ASSET_EXAMPLE, "asset_id": "example-chair", "source": "example"},
                 "score": 0.25, "retrieval_sources": ["clip_text_to_preview"],
                 "explanation": "Ví dụ cấu trúc response cosine CLIP; không phải kết quả đo thật."}],
}
router = APIRouter(prefix="/api/v1", responses=ERRORS)


def text_parameters(value: LiveTextSearchRequest) -> LiveTextSearchRequest:
    return value


def retrieve_candidates(request: Request, value: Annotated[LiveTextSearchRequest, Depends(text_parameters)]) -> TextSearchCandidates:
    service = request.app.state.text_search_service
    if service is None:
        raise unavailable()
    try:
        result = service.search_text(value.query, value.filters.model_copy(deep=True), candidate_limit=TEXT_CANDIDATE_LIMIT)
        # Revalidate even a mutated/constructed Pydantic object from an adapter.
        return TextSearchCandidates.model_validate(result.model_dump() if isinstance(result, TextSearchCandidates) else result)
    except SearchUnavailable:
        raise unavailable() from None
    except Exception as exc:
        logger.error("Text retrieval failed: %s", type(exc).__name__)
        raise api_error(500, "INTERNAL_ERROR", "Lỗi máy chủ. Vui lòng thử lại sau.") from None


def text_session(request: Request, candidates: Annotated[TextSearchCandidates, Depends(retrieve_candidates)]) -> Iterator[Session]:
    # Invalid input/service readiness must be resolved before opening a DB session.
    yield from get_db_session(request)


@router.post("/search/text", response_model=LiveTextSearchResponse, tags=["search"],
             summary="Tìm kiếm văn bản qua search service",
             description="Tối đa 200 ứng viên, metadata PostgreSQL và event durable. Trả 503 nếu adapter/index chưa sẵn sàng; không fallback mock.",
             responses={200: response_example(EXAMPLE)})
def search_text(
    value: Annotated[LiveTextSearchRequest, Depends(text_parameters)],
    candidates: Annotated[TextSearchCandidates, Depends(retrieve_candidates)],
    session: Annotated[Session, Depends(text_session)],
):
    return execute_text_search(session, value, candidates)
