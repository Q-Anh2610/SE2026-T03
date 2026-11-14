"""Lưu vòng đời jobs của batch runner, không thay dữ liệu assets/search/feedback.

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("runner", sa.String(80), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("processed", sa.BigInteger(), nullable=True),
        sa.Column("total", sa.BigInteger(), nullable=True),
        sa.Column("result", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("error", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("job_id", name=op.f("pk_jobs")),
        sa.CheckConstraint("kind IN ('ingestion', 'indexing')", name=op.f("ck_jobs_kind")),
        sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name=op.f("ck_jobs_status")),
        sa.CheckConstraint("processed IS NULL OR processed >= 0", name=op.f("ck_jobs_processed_nonnegative")),
        sa.CheckConstraint("total IS NULL OR total >= 0", name=op.f("ck_jobs_total_nonnegative")),
        sa.CheckConstraint("processed IS NULL OR total IS NULL OR processed <= total", name=op.f("ck_jobs_progress_bounds")),
        sa.CheckConstraint("(status = 'queued' AND started_at IS NULL AND finished_at IS NULL) OR "
                           "(status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
                           "(status IN ('succeeded', 'failed') AND started_at IS NOT NULL AND finished_at IS NOT NULL)",
                           name=op.f("ck_jobs_lifecycle")),
        sa.CheckConstraint("(status = 'failed' AND error IS NOT NULL) OR (status <> 'failed' AND error IS NULL)",
                           name=op.f("ck_jobs_error_state")),
        sa.CheckConstraint("started_at IS NULL OR started_at >= created_at", name=op.f("ck_jobs_start_order")),
        sa.CheckConstraint("finished_at IS NULL OR finished_at >= started_at", name=op.f("ck_jobs_finish_order")),
    )
    op.create_index("ix_jobs_created_job", "jobs", ["created_at", "job_id"])


def downgrade():
    op.drop_index("ix_jobs_created_job", table_name="jobs")
    op.drop_table("jobs")
