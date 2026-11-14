"""Đọc jobs PostgreSQL theo snapshot và ghi các chuyển trạng thái riêng transaction."""

from uuid import UUID

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models import Job
from app.schemas.api import Pagination
from app.schemas.jobs import JobDetailResponse, JobListQuery, JobListResponse, JobMetadata, JobProgress


def job_metadata(job: Job) -> JobMetadata:
    percent = None if not job.total or job.processed is None else round(job.processed * 100 / job.total, 2)
    return JobMetadata(
        job_id=job.job_id, kind=job.kind, runner=job.runner, status=job.status,
        created_at=job.created_at, updated_at=job.updated_at,
        started_at=job.started_at, finished_at=job.finished_at,
        progress=JobProgress(processed=job.processed, total=job.total, percent=percent),
        result=job.result, error=job.error,
    )


def list_jobs(session: Session, params: JobListQuery) -> JobListResponse:
    conditions = [getattr(Job, key) == getattr(params, key) for key in ("kind", "status")
                  if getattr(params, key) is not None]
    total = session.scalar(select(func.count()).select_from(Job).where(*conditions))
    offset = (params.page - 1) * params.limit
    rows = [] if offset >= total else session.scalars(
        select(Job).where(*conditions).order_by(Job.created_at.desc(), Job.job_id.desc())
        .offset(offset).limit(params.limit)
    ).all()
    pages = (total + params.limit - 1) // params.limit
    return JobListResponse(items=[job_metadata(row) for row in rows],
        pagination=Pagination(page=params.page, limit=params.limit, total=total,
                              pages=pages, has_next=params.page < pages))


def get_job(session: Session, job_id: UUID) -> JobDetailResponse:
    job = session.get(Job, job_id)
    if job is None:
        raise api_error(404, "JOB_NOT_FOUND", "Không tìm thấy job.")
    return JobDetailResponse(job=job_metadata(job))


def create_job(engine: Engine, *, kind: str, runner: str) -> UUID:
    # Commit trước thực thi: reader ở tiến trình khác nhìn được queued/running.
    with Session(engine) as session, session.begin():
        job = Job(kind=kind, runner=runner, status="queued")
        session.add(job)
        session.flush()
        return job.job_id


def start_job(engine: Engine, job_id: UUID) -> None:
    with Session(engine) as session, session.begin():
        job = session.get(Job, job_id, with_for_update=True)
        if job is None or job.status != "queued":
            raise ValueError("Only queued jobs can start.")
        job.status = "running"
        job.started_at = func.clock_timestamp()


def finish_job(engine: Engine, job_id: UUID, *, result=None, error=None,
               processed=None, total=None) -> None:
    with Session(engine) as session, session.begin():
        job = session.get(Job, job_id, with_for_update=True)
        if job is None or job.status != "running":
            raise ValueError("Only running jobs can finish.")
        job.status = "failed" if error is not None else "succeeded"
        job.finished_at = func.clock_timestamp()
        job.result, job.error = result, error
        job.processed, job.total = processed, total
