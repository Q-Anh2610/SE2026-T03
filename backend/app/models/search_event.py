from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.feedback import Feedback


class SearchEvent(Base):
    __tablename__ = "search_events"
    __table_args__ = (
        CheckConstraint("query_type IN ('text', 'image')", name="query_type"),
        CheckConstraint(
            "(query_type = 'text' AND query_text IS NOT NULL AND length(trim(query_text)) > 0) OR "
            "(query_type = 'image' AND query_image_ref IS NOT NULL AND length(trim(query_image_ref)) > 0)",
            name="query_present",
        ),
    )

    search_event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    query_type: Mapped[str] = mapped_column(String(16))
    query_text: Mapped[str | None] = mapped_column(Text)
    query_image_ref: Mapped[str | None] = mapped_column(Text)
    filters: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict, server_default=text("'{}'::jsonb"))
    model_version: Mapped[str] = mapped_column(Text)
    index_version: Mapped[str] = mapped_column(Text)
    config_version: Mapped[str] = mapped_column(Text)
    dataset_snapshot: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="search_event", passive_deletes="all")
