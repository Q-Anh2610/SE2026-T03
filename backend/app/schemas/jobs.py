"""DTO jobs/status W5; null nghĩa chưa được runner đo, không suy ra phần trăm."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.api import InputModel, Pagination

JobKind = Literal["ingestion", "indexing"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]


class JobListQuery(InputModel):
    kind: JobKind | None = None
    status: JobStatus | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=12, ge=1, le=50)


class JobProgress(BaseModel):
    unit: Literal["assets"] = "assets"
    processed: int | None = Field(ge=0)
    total: int | None = Field(ge=0)
    percent: float | None = Field(ge=0, le=100)


class JobResult(BaseModel):
    index_version: str | None = None
    model_version: str | None = None
    dataset_snapshot: str | None = None
    asset_count: int | None = Field(default=None, ge=0)
    point_count: int | None = Field(default=None, ge=0)
    index_ref: str | None = None
    index_manifest_sha256: str | None = None
    search_verified: bool | None = None
    persistence: Literal["postgresql", "local_files_only"] | None = None
    input_count: int | None = Field(default=None, ge=0)
    succeeded: int | None = Field(default=None, ge=0)
    failed: int | None = Field(default=None, ge=0)
    skipped: int | None = Field(default=None, ge=0)
    manifest_sha256: str | None = None
    exit_code: int | None = None


class JobError(BaseModel):
    code: str
    message: str


class JobMetadata(BaseModel):
    job_id: UUID
    kind: JobKind
    runner: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    progress: JobProgress
    result: JobResult | None
    error: JobError | None


class JobListResponse(BaseModel):
    items: list[JobMetadata]
    pagination: Pagination
    mock: Literal[False] = False


class JobDetailResponse(BaseModel):
    job: JobMetadata
    mock: Literal[False] = False
