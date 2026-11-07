"""API feedback durable cho search event text/image."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy.orm import Session

from app.api.examples import response_example
from app.db.dependencies import get_db_session
from app.schemas.api import ErrorResponse
from app.schemas.feedback import LiveFeedbackRequest, LiveFeedbackResponse
from app.services.feedback import record_feedback

EXAMPLE = {
    "feedback_id": "00000000-0000-4000-8000-000000000081",
    "search_event_id": "00000000-0000-4000-8000-000000000080",
    "asset_id": "example-chair", "relevance": True,
    "created_at": "2026-11-07T00:00:00Z", "storage": "postgresql", "mock": False,
}
ERRORS = {
    status: {"model": ErrorResponse, **response_example({"error": {
        "code": code, "message": message, "details": [],
    }})}
    for status, code, message in (
        (400, "EVENT_ASSET_MISMATCH", "Asset không thuộc kết quả của truy vấn này."),
        (404, "SEARCH_EVENT_NOT_FOUND", "Không tìm thấy truy vấn. Hãy tìm kiếm lại."),
        (500, "INTERNAL_ERROR", "Lỗi máy chủ. Vui lòng thử lại sau."),
    )
}
router = APIRouter(prefix="/api/v1", responses=ERRORS)


def feedback_parameters(
    value: Annotated[LiveFeedbackRequest, Body(openapi_examples={
        "relevant": {"summary": "Thay IDs bằng event và asset từ kết quả search thật",
                     "value": {"search_event_id": EXAMPLE["search_event_id"],
                               "asset_id": EXAMPLE["asset_id"], "relevance": True}},
    })],
) -> LiveFeedbackRequest:
    return value


def feedback_session(request: Request,
                     value: Annotated[LiveFeedbackRequest, Depends(feedback_parameters)]) -> Iterator[Session]:
    yield from get_db_session(request)


@router.post("/feedback", response_model=LiveFeedbackResponse, status_code=201, tags=["feedback"],
    summary="Lưu phản hồi vào PostgreSQL",
    description="Mỗi lần gửi hợp lệ tạo phản hồi mới, kể cả gửi lại/đổi đánh giá. Asset phải thuộc đúng trang kết quả của event. Event cũ chưa có result snapshot trả 400 SEARCH_EVENT_RESULTS_UNAVAILABLE; request sai trả 400 INVALID_REQUEST.",
    responses={201: response_example(EXAMPLE)})
def send_feedback(value: Annotated[LiveFeedbackRequest, Depends(feedback_parameters)],
                  session: Annotated[Session, Depends(feedback_session)]):
    return record_feedback(session, value)
