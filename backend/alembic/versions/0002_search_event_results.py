"""Lưu asset IDs của trang kết quả để xác minh feedback.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Event cũ giữ NULL: chưa có snapshot kết quả để xác minh feedback.
    op.add_column("search_events", sa.Column("result_asset_ids",
        postgresql.JSONB(none_as_null=True), nullable=True))
    op.create_check_constraint(
        op.f("ck_search_events_result_asset_ids_array"), "search_events",
        "result_asset_ids IS NULL OR jsonb_typeof(result_asset_ids) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_search_events_result_asset_ids_array"), "search_events", type_="check")
    op.drop_column("search_events", "result_asset_ids")
