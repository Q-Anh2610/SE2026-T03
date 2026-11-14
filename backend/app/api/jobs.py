"""Read-only jobs/status; xác thực trước validation và kết nối DB."""

from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.examples import response_example
from app.core.admin import require_admin
from app.db.dependencies import get_db_session
from app.schemas.api import ErrorResponse
from app.schemas.jobs import JobDetailResponse, JobListQuery, JobListResponse
from app.services.jobs import get_job, list_jobs

ERRORS = {
    status: {"model": ErrorResponse, **response_example({"error": {"code": code, "message": message, "details": []}})}
    for status, code, message in (
        (400, "INVALID_REQUEST", "Yêu cầu không hợp lệ."),
        (403, "ADMIN_ACCESS_DENIED", "Không có quyền truy cập quản trị."),
        (404, "JOB_NOT_FOUND", "Không tìm thấy job."),
        (500, "INTERNAL_ERROR", "Lỗi máy chủ. Vui lòng thử lại sau."),
        (503, "ADMIN_API_UNAVAILABLE", "API quản trị chưa được cấu hình."),
    )
}
EXAMPLE = {
    "job_id": "a0b674d2-1286-401f-b73b-72cae159fcad", "kind": "ingestion",
    "runner": "ingestion.run_batch", "status": "succeeded",
    "created_at": "2026-11-14T08:00:00Z", "updated_at": "2026-11-14T08:01:00Z",
    "started_at": "2026-11-14T08:00:01Z", "finished_at": "2026-11-14T08:01:00Z",
    "progress": {"unit": "assets", "processed": 2, "total": 2, "percent": 100.0},
    "result": {"persistence": "postgresql", "input_count": 2, "succeeded": 1, "failed": 0, "skipped": 1,
               "manifest_sha256": "a" * 64, "exit_code": None},
    "error": None,
}
router = APIRouter(prefix="/api/v1/admin/jobs", tags=["admin jobs"],
                   dependencies=[Depends(require_admin)], responses=ERRORS)


def list_parameters(params: Annotated[JobListQuery, Query()]) -> JobListQuery:
    return params


def list_session(request: Request, params: Annotated[JobListQuery, Depends(list_parameters)]) -> Iterator[Session]:
    yield from get_db_session(request)


def identifier(job_id: UUID) -> UUID:
    return job_id


def detail_session(request: Request, job_id: Annotated[UUID, Depends(identifier)]) -> Iterator[Session]:
    yield from get_db_session(request)


@router.get("", response_model=JobListResponse, summary="Danh sách jobs từ PostgreSQL",
            description="Lọc AND theo kind/status; created_at DESC, job_id DESC. Không fallback fixture.",
            responses={200: response_example({"items": [EXAMPLE], "mock": False,
                "pagination": {"page": 1, "limit": 12, "total": 1, "pages": 1, "has_next": False}})})
def jobs(params: Annotated[JobListQuery, Depends(list_parameters)],
         session: Annotated[Session, Depends(list_session)]):
    return list_jobs(session, params)


@router.get("/{job_id}", response_model=JobDetailResponse, summary="Chi tiết job từ PostgreSQL",
            responses={200: response_example({"job": EXAMPLE, "mock": False})})
def job_detail(job_id: Annotated[UUID, Depends(identifier)],
               session: Annotated[Session, Depends(detail_session)]):
    return get_job(session, job_id)
