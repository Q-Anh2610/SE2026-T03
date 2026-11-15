"""Lịch sử thực thi runner; độc lập với ingestion_status của từng asset."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("kind IN ('ingestion', 'indexing')", name="kind"),
        CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="status"),
        CheckConstraint("processed IS NULL OR processed >= 0", name="processed_nonnegative"),
        CheckConstraint("total IS NULL OR total >= 0", name="total_nonnegative"),
        CheckConstraint("processed IS NULL OR total IS NULL OR processed <= total", name="progress_bounds"),
        CheckConstraint("(status = 'queued' AND started_at IS NULL AND finished_at IS NULL) OR "
                        "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
                        "(status IN ('succeeded', 'failed') AND started_at IS NOT NULL AND finished_at IS NOT NULL)",
                        name="lifecycle"),
        CheckConstraint("(status = 'failed' AND error IS NOT NULL) OR (status <> 'failed' AND error IS NULL)",
                        name="error_state"),
        CheckConstraint("started_at IS NULL OR started_at >= created_at", name="start_order"),
        CheckConstraint("finished_at IS NULL OR finished_at >= started_at", name="finish_order"),
        Index("ix_jobs_created_job", "created_at", "job_id"),
        Index("uq_jobs_request_id", "request_id", unique=True),
        Index("uq_jobs_active_resource", "resource_key", unique=True,
              postgresql_where=text("resource_key IS NOT NULL AND status IN ('queued', 'running')")),
    )

    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(16))
    runner: Mapped[str] = mapped_column(String(80))
    request_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    resource_key: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    processed: Mapped[int | None] = mapped_column(BigInteger)
    total: Mapped[int | None] = mapped_column(BigInteger)
    result: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    error: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.clock_timestamp())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
