from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.search_event import SearchEvent


class Feedback(Base):
    __tablename__ = "feedbacks"

    feedback_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    search_event_id: Mapped[UUID] = mapped_column(ForeignKey("search_events.search_event_id", ondelete="RESTRICT"), index=True)
    asset_id: Mapped[str] = mapped_column(String(128), ForeignKey("assets.asset_id", ondelete="RESTRICT"), index=True)
    relevance: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset: Mapped["Asset"] = relationship(back_populates="feedbacks")
    search_event: Mapped["SearchEvent"] = relationship(back_populates="feedbacks")
