"""Request idempotency và khóa tài nguyên reindex; giữ nguyên lịch sử jobs cũ."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("jobs", sa.Column("resource_key", sa.String(128), nullable=True))
    op.create_index("uq_jobs_request_id", "jobs", ["request_id"], unique=True)
    op.create_index("uq_jobs_active_resource", "jobs", ["resource_key"], unique=True,
                    postgresql_where=sa.text("resource_key IS NOT NULL AND status IN ('queued', 'running')"))


def downgrade():
    op.drop_index("uq_jobs_active_resource", table_name="jobs")
    op.drop_index("uq_jobs_request_id", table_name="jobs")
    op.drop_column("jobs", "resource_key")
    op.drop_column("jobs", "request_id")
