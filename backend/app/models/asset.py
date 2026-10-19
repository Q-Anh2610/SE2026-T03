from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.feedback import Feedback


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_assets_source_source_id"),
        CheckConstraint("face_count IS NULL OR face_count >= 0", name="face_count_nonnegative"),
        Index("ix_assets_category", "category"),
        Index("ix_assets_license", "license"),
        Index("ix_assets_face_count", "face_count"),
    )

    asset_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(MutableList.as_mutable(ARRAY(Text)), default=list, server_default=text("'{}'::text[]"))
    category: Mapped[str | None] = mapped_column(Text)
    thumbnail_path: Mapped[str | None] = mapped_column(Text)
    model_path: Mapped[str | None] = mapped_column(Text)
    face_count: Mapped[int | None] = mapped_column(BigInteger)
    checksum: Mapped[str | None] = mapped_column(String(64))
    ingestion_status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending")
    formats: Mapped[list[str]] = mapped_column(MutableList.as_mutable(ARRAY(Text)), default=list, server_default=text("'{}'::text[]"))
    model_version: Mapped[str | None] = mapped_column(Text)
    index_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="asset", passive_deletes="all")
