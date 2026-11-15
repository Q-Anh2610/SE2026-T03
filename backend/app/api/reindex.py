"""POST kích hoạt reindex nội bộ; trả job ID, worker thực thi sau commit."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.exc import SQLAlchemyError

from app.api.examples import response_example
from app.api.jobs import ERRORS
from app.core.admin import require_admin
from app.core.errors import api_error
from app.db.session import create_db_engine
from app.schemas.api import ErrorResponse
from app.schemas.reindex import ReindexRequest, ReindexResponse
from app.services.reindex import ReindexManager, validate_configuration

EXAMPLE = {"job_id": "a0b674d2-1286-401f-b73b-72cae159fcad", "status": "queued",
           "status_url": "/api/v1/admin/jobs/a0b674d2-1286-401f-b73b-72cae159fcad", "reused": False}
router = APIRouter(prefix="/api/v1/admin", tags=["admin reindex"], dependencies=[Depends(require_admin)],
    responses={**{code: value for code, value in ERRORS.items() if code != 404},
        409: {"model": ErrorResponse, **response_example({"error": {
        "code": "REINDEX_IN_PROGRESS", "message": "Đã có lượt reindex trên tài nguyên này.", "details": []}})},
        503: {"model": ErrorResponse, **response_example({"error": {
            "code": "REINDEX_UNAVAILABLE", "message": "Reindex chưa được cấu hình sẵn sàng.", "details": []}})}})


def parameters(value: ReindexRequest) -> ReindexRequest:
    return value


@router.post("/reindex", status_code=202, response_model=ReindexResponse,
    summary="Dựng index CLIP candidate 200 riêng và theo dõi job",
    description="Không chuyển active index. request_id UUID chống gửi trùng; cùng request trả job cũ (200), request khác khi bận trả 409. Không nhận URL/path/command/model tùy ý.",
    responses={202: response_example(EXAMPLE), 200: {"model": ReindexResponse,
        **response_example({**EXAMPLE, "reused": True})}})
def reindex(request: Request, response: Response, value: Annotated[ReindexRequest, Depends(parameters)]):
    settings = request.app.state.settings
    validate_configuration(settings)
    try:
        with request.app.state.db_engine_lock:
            if request.app.state.db_engine is None:
                request.app.state.db_engine = create_db_engine(settings)
            if request.app.state.reindex_manager is None:
                request.app.state.reindex_manager = ReindexManager(request.app.state.db_engine, settings,
                    operation=request.app.state.reindex_operation)
            manager = request.app.state.reindex_manager
        result = manager.submit(value)
    except (SQLAlchemyError, ValueError):
        raise api_error(500, "INTERNAL_ERROR", "Không ghi được yêu cầu reindex.") from None
    response.status_code = 200 if result.reused else 202
    return result
