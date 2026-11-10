"""Contract feedback PostgreSQL, kế thừa payload và append semantics mock v1."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, StrictBool

from app.schemas.api import InputModel


class LiveFeedbackRequest(InputModel):
    search_event_id: UUID
    asset_id: str = Field(min_length=1, max_length=128)
    relevance: StrictBool


class LiveFeedbackResponse(BaseModel):
    feedback_id: UUID
    search_event_id: UUID
    asset_id: str
    relevance: StrictBool
    created_at: AwareDatetime
    storage: Literal["postgresql"]
    mock: Literal[False]
