"""Lưu một text search đã retrieval thành công; caller sở hữu/đóng session."""

import logging
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models import SearchEvent
from app.schemas.text_search import LiveTextSearchRequest, SearchExecutionVersions
from app.schemas.image_search import LiveImageSearchRequest

logger = logging.getLogger(__name__)


def persist_text_search_event(
    session: Session, request: LiveTextSearchRequest, versions: SearchExecutionVersions,
) -> UUID:
    """Commit trước HTTP 200. Dùng session riêng theo request, không commit việc khác.

    Chỉ gọi sau retrieval + mapping/response validation; cả kết quả rỗng/trang
    vượt phạm vi vẫn tạo event. Lỗi validation/retrieval không gọi hàm này.
    Không đóng session ở đây: get_db_session/context manager giải phóng pool.
    """
    # Revalidate ngay biên persistence, kể cả caller dùng model_construct hoặc
    # sửa model sau validation. Không chấp nhận defaults mock/versions rỗng.
    request = LiveTextSearchRequest.model_validate(request.model_dump())
    versions = SearchExecutionVersions.model_validate(versions.model_dump())
    identifier = uuid4()
    event = SearchEvent(
        search_event_id=identifier, query_type="text", query_text=request.query,
        query_image_ref=None, filters=request.filters.model_dump(exclude_none=True),
        **versions.model_dump(),
    )
    return _commit_event(session, event)


def persist_image_search_event(
    session: Session, request: LiveImageSearchRequest, versions: SearchExecutionVersions,
) -> UUID:
    request = LiveImageSearchRequest.model_validate(request.model_dump())
    versions = SearchExecutionVersions.model_validate(versions.model_dump())
    event = SearchEvent(
        search_event_id=uuid4(), query_type="image", query_text=None,
        query_image_ref=request.query_image_ref, filters=request.filters.model_dump(exclude_none=True),
        **versions.model_dump(),
    )
    return _commit_event(session, event)


def _commit_event(session: Session, event: SearchEvent) -> UUID:
    if session.new or session.dirty or session.deleted:
        raise ValueError("Search event persistence requires a session without pending writes.")
    identifier = event.search_event_id
    try:
        session.add(event)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        # Không log query, filters, exception text, SQL hoặc URL kết nối.
        logger.error("Search event persistence failed: %s", type(exc).__name__)
        raise api_error(500, "INTERNAL_ERROR", "Lỗi máy chủ. Vui lòng thử lại sau.") from None
    return identifier
