"""Contract mock v1; search response giữ shape frontend tuần 1 đang đọc."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AssetFilters(InputModel):
    category: str | None = Field(default=None, min_length=1)
    license: str | None = Field(default=None, min_length=1)
    format: str | None = Field(default=None, min_length=1)
    face_count_min: int | None = Field(default=None, ge=0)
    face_count_max: int | None = Field(default=None, ge=0)

    @field_validator("face_count_min", "face_count_max", mode="before")
    @classmethod
    def reject_boolean_count(cls, value):
        if isinstance(value, bool):
            raise ValueError("Face count must be an integer.")
        return value

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if self.face_count_min is not None and self.face_count_max is not None:
            if self.face_count_min > self.face_count_max:
                raise ValueError("face_count_min must not exceed face_count_max.")
        return self


class AssetListQuery(AssetFilters):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=12, ge=1, le=50)


class TextSearchRequest(InputModel):
    query: str = Field(min_length=1, max_length=500, examples=["ghế gỗ"])
    filters: AssetFilters = Field(default_factory=AssetFilters)
    page: int = Field(default=1, ge=1, strict=True)
    limit: int = Field(default=12, ge=1, le=50, strict=True)


class AssetMetadata(BaseModel):
    asset_id: str
    name: str
    description: str | None
    category: str | None
    tags: list[str]
    formats: list[str]
    face_count: int | None = Field(ge=0)
    thumbnail_url: str | None
    source: str
    source_url: str | None
    author: str | None
    license: str | None


class Pagination(BaseModel):
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=50)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)
    has_next: bool


class AssetListResponse(BaseModel):
    items: list[AssetMetadata]
    pagination: Pagination
    mock: bool = False


class AssetDetailResponse(BaseModel):
    asset: AssetMetadata
    mock: Literal[True] = True


class Versions(BaseModel):
    model_version: str = "mock-no-encoder"
    index_version: str = "mock-w1"
    config_version: str = "mock-contract-v1"


class SearchResult(BaseModel):
    rank: int = Field(ge=1)
    asset: AssetMetadata
    retrieval_sources: list[str]
    explanation: str
    score: float | None = Field(default=None, allow_inf_nan=False)


class SearchResponse(BaseModel):
    query_id: str
    search_event_id: str
    query: str
    results: list[SearchResult]
    versions: Versions
    pagination: Pagination
    mock: Literal[True] = True


class FeedbackRequest(InputModel):
    search_event_id: str = Field(min_length=1, examples=["mock-event-example"])
    asset_id: str = Field(min_length=1, examples=["mock-chair-01"])
    relevance: StrictBool = Field(description="true=phù hợp, false=không phù hợp; không phải nhãn benchmark 0/1/2")


class FeedbackResponse(BaseModel):
    feedback_id: str
    search_event_id: str
    asset_id: str
    relevance: bool
    created_at: datetime
    storage: Literal["memory"] = "memory"
    mock: Literal[True] = True


class ErrorField(BaseModel):
    field: str
    message: str


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: list[ErrorField] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorInfo
