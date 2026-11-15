"""Contract kích hoạt một profile reindex cố định; không nhận path/URL/command."""

from typing import Literal
from uuid import UUID

from app.schemas.api import InputModel
from app.schemas.jobs import JobStatus
from pydantic import BaseModel


class ReindexRequest(InputModel):
    request_id: UUID
    profile: Literal["clip-candidate200-v1"] = "clip-candidate200-v1"


class ReindexResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    status_url: str
    reused: bool
