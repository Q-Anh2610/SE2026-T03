"""Session theo request; engine được tạo lười và đóng theo vòng đời ứng dụng."""

import logging
from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.db.session import create_db_engine

logger = logging.getLogger(__name__)


def get_db_session(request: Request) -> Iterator[Session]:
    try:
        # Sync dependencies có thể chạy ở nhiều worker threads cùng lúc.
        with request.app.state.db_engine_lock:
            if request.app.state.db_engine is None:
                request.app.state.db_engine = create_db_engine(request.app.state.settings)
            engine = request.app.state.db_engine
        # Count và trang dữ liệu dùng chung snapshot, kể cả khi ingestion đang ghi.
        with Session(engine.execution_options(isolation_level="REPEATABLE READ")) as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise
    except (SQLAlchemyError, ValueError) as exc:
        # Không log exception text/traceback vì có thể chứa credentials hoặc SQL.
        logger.error("Asset database request failed: %s", type(exc).__name__)
        raise api_error(500, "INTERNAL_ERROR", "Lỗi máy chủ. Vui lòng thử lại sau.") from None
