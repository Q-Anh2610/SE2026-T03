"""Contract text search thật W3; chưa thay route mock của Issue #9."""

from math import ceil
from typing import ClassVar, Literal, Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.api import AssetFilters, Pagination, SearchResult, TextSearchRequest


TEXT_CANDIDATE_LIMIT = 200


class TextSearchFilters(AssetFilters):
    # JSON body phải là integer; query string của list API vẫn được parse riêng.
    face_count_min: int | None = Field(default=None, ge=0, strict=True)
    face_count_max: int | None = Field(default=None, ge=0, strict=True)


class LiveTextSearchRequest(TextSearchRequest):
    filters: TextSearchFilters = Field(default_factory=TextSearchFilters)


class SearchExecutionVersions(BaseModel):
    """Lấy từ cấu hình thực sự dùng để retrieval, không dùng defaults mock."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)
    model_version: str = Field(min_length=1)
    index_version: str = Field(min_length=1)
    config_version: str = Field(min_length=1)
    dataset_snapshot: str = Field(min_length=1)

    @field_validator("model_version", "index_version", "config_version", "dataset_snapshot")
    @classmethod
    def real_version(cls, value: str) -> str:
        if value.casefold().startswith("mock-"):
            raise ValueError("Live execution cannot use mock versions.")
        return value


class TextSearchHit(BaseModel):
    """Interface service #60 → API: ứng viên trước mapping metadata DB."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    asset_id: str = Field(min_length=1, max_length=128)
    score: float = Field(ge=-1, le=1, allow_inf_nan=False)

    @field_validator("asset_id")
    @classmethod
    def detail_compatible_id(cls, value: str) -> str:
        if value != value.strip() or value in {".", ".."} or any(c in value for c in "/\\?#%"):
            raise ValueError("Asset ID must be usable as one detail URL segment.")
        return value


class TextSearchCandidates(BaseModel):
    """Top 200 sau filters/dedup; score giảm dần, hòa score theo asset_id."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    hits: list[TextSearchHit] = Field(max_length=TEXT_CANDIDATE_LIMIT)
    versions: SearchExecutionVersions

    @model_validator(mode="after")
    def ordered_unique(self) -> Self:
        ids = [hit.asset_id for hit in self.hits]
        if len(ids) != len(set(ids)):
            raise ValueError("Candidate asset IDs must be unique.")
        if self.hits != sorted(self.hits, key=lambda hit: (-hit.score, hit.asset_id)):
            raise ValueError("Candidates must be ordered by score descending, then asset_id.")
        return self


class LiveTextSearchResponse(BaseModel):
    retrieval_source: ClassVar[str] = "clip_text_to_preview"
    model_config = ConfigDict(extra="forbid")
    query_id: UUID
    search_event_id: UUID
    query: str = Field(min_length=1, max_length=500)
    results: list[SearchResult]
    versions: SearchExecutionVersions
    pagination: Pagination
    mock: Literal[False]  # Bắt buộc, không default để che lỗi mapping.

    @field_validator("mock", mode="before")
    @classmethod
    def explicitly_false(cls, value):
        if value is not False:
            raise ValueError("Live response requires JSON boolean false.")
        return value

    @model_validator(mode="after")
    def page_invariants(self) -> Self:
        p = self.pagination
        expected = min(p.limit, max(0, p.total - (p.page - 1) * p.limit))
        if self.query != self.query.strip() or self.query_id != self.search_event_id:
            raise ValueError("Query must be normalized and query/event IDs must match.")
        if p.total > TEXT_CANDIDATE_LIMIT or p.pages != ceil(p.total / p.limit) or p.has_next != (p.page < p.pages):
            raise ValueError("Pagination must describe the bounded candidate window.")
        if len(self.results) != expected or [r.rank for r in self.results] != list(range(1, expected + 1)):
            raise ValueError("Result count and page-relative ranks must match pagination.")
        hits = []
        for result in self.results:
            hits.append(TextSearchHit(asset_id=result.asset.asset_id, score=result.score))
            if not result.asset.name.strip() or not result.asset.source.strip():
                raise ValueError("Asset name and source must be nonempty.")
            if result.retrieval_sources != [self.retrieval_source] or not result.explanation.strip():
                raise ValueError("Live result must describe the actual CLIP retrieval source.")
            for url in (result.asset.source_url, result.asset.thumbnail_url):
                if url is not None:
                    parsed = urlsplit(url)
                    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
                        raise ValueError("Public asset URLs must be HTTP(S) without credentials.")
        TextSearchCandidates(hits=hits, versions=self.versions)
        return self
