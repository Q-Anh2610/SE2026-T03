"""Tạo assets, search_events và feedbacks.

Revision ID: 0001
Revises: None
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("asset_id", sa.String(128), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("thumbnail_path", sa.Text(), nullable=True),
        sa.Column("model_path", sa.Text(), nullable=True),
        sa.Column("face_count", sa.BigInteger(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("ingestion_status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("formats", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("index_version", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("asset_id", name=op.f("pk_assets")),
        sa.UniqueConstraint("source", "source_id", name="uq_assets_source_source_id"),
        sa.CheckConstraint("face_count IS NULL OR face_count >= 0", name=op.f("ck_assets_face_count_nonnegative")),
    )
    for column in ("category", "license", "face_count"):
        op.create_index(f"ix_assets_{column}", "assets", [column])

    op.create_table(
        "search_events",
        sa.Column("search_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_type", sa.String(16), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column("query_image_ref", sa.Text(), nullable=True),
        sa.Column("filters", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("index_version", sa.Text(), nullable=False),
        sa.Column("config_version", sa.Text(), nullable=False),
        sa.Column("dataset_snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("search_event_id", name=op.f("pk_search_events")),
        sa.CheckConstraint("query_type IN ('text', 'image')", name=op.f("ck_search_events_query_type")),
        sa.CheckConstraint(
            "(query_type = 'text' AND query_text IS NOT NULL AND length(trim(query_text)) > 0) OR "
            "(query_type = 'image' AND query_image_ref IS NOT NULL AND length(trim(query_image_ref)) > 0)",
            name=op.f("ck_search_events_query_present"),
        ),
    )
    op.create_index("ix_search_events_created_at", "search_events", ["created_at"])

    op.create_table(
        "feedbacks",
        sa.Column("feedback_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("search_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", sa.String(128), nullable=False),
        sa.Column("relevance", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("feedback_id", name=op.f("pk_feedbacks")),
        sa.ForeignKeyConstraint(["search_event_id"], ["search_events.search_event_id"], ondelete="RESTRICT", name=op.f("fk_feedbacks_search_event_id_search_events")),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"], ondelete="RESTRICT", name=op.f("fk_feedbacks_asset_id_assets")),
    )
    op.create_index("ix_feedbacks_search_event_id", "feedbacks", ["search_event_id"])
    op.create_index("ix_feedbacks_asset_id", "feedbacks", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_feedbacks_asset_id", table_name="feedbacks")
    op.drop_index("ix_feedbacks_search_event_id", table_name="feedbacks")
    op.drop_table("feedbacks")
    op.drop_index("ix_search_events_created_at", table_name="search_events")
    op.drop_table("search_events")
    for column in ("face_count", "license", "category"):
        op.drop_index(f"ix_assets_{column}", table_name="assets")
    op.drop_table("assets")
