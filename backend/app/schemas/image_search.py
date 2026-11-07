"""DTO API ảnh thật; provenance/ranking dùng cùng quy tắc text search."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.text_search import LiveTextSearchResponse, TextSearchFilters


class LiveImageSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_image_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    filters: TextSearchFilters = Field(default_factory=TextSearchFilters)
    page: int = Field(default=1, ge=1, strict=True)
    limit: int = Field(default=12, ge=1, le=50, strict=True)


class LiveImageSearchResponse(LiveTextSearchResponse):
    retrieval_source: ClassVar[str] = "clip_image_to_preview"
    query: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
