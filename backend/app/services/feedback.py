"""Ghi phản hồi mới sau khi kiểm tra event và asset trong cùng transaction."""

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models import Asset, Feedback, SearchEvent
from app.schemas.feedback import LiveFeedbackRequest, LiveFeedbackResponse

logger = logging.getLogger(__name__)


def record_feedback(session: Session, value: LiveFeedbackRequest) -> LiveFeedbackResponse:
    value = LiveFeedbackRequest.model_validate(value.model_dump())
    if session.new or session.dirty or session.deleted:
        raise ValueError("Feedback requires a session without pending writes.")
    try:
        # SHARE khóa snapshot event đến commit và cho phép nhiều feedback đọc
        # đồng thời. KEY SHARE bảo vệ asset khỏi bị xóa trong lúc ghi FK.
        event = session.scalar(select(SearchEvent).where(
            SearchEvent.search_event_id == value.search_event_id).with_for_update(read=True))
        if event is None:
            raise api_error(404, "SEARCH_EVENT_NOT_FOUND", "Không tìm thấy truy vấn. Hãy tìm kiếm lại.")
        asset = session.scalar(select(Asset).where(
            Asset.asset_id == value.asset_id).with_for_update(read=True, key_share=True))
        if asset is None:
            raise api_error(404, "ASSET_NOT_FOUND", "Không tìm thấy asset.")
        if event.result_asset_ids is None:
            raise api_error(400, "SEARCH_EVENT_RESULTS_UNAVAILABLE",
                "Truy vấn cũ chưa có dữ liệu xác minh kết quả. Hãy tìm kiếm lại.")
        if value.asset_id not in event.result_asset_ids:
            raise api_error(400, "EVENT_ASSET_MISMATCH", "Asset không thuộc kết quả của truy vấn này.")
        feedback = Feedback(**value.model_dump())
        session.add(feedback)
        session.flush()  # Nhận UUID và created_at do DB cấp trước khi validate response.
        response = LiveFeedbackResponse(
            feedback_id=feedback.feedback_id, search_event_id=feedback.search_event_id,
            asset_id=feedback.asset_id, relevance=feedback.relevance, created_at=feedback.created_at,
            storage="postgresql", mock=False,
        )
        response.model_dump_json()
        session.commit()
        return response
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("Feedback persistence failed: %s", type(exc).__name__)
        raise api_error(500, "INTERNAL_ERROR", "Lỗi máy chủ. Vui lòng thử lại sau.") from None
