from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .db.models import ArtifactKind, EventLevel, JobStatus, JobStep, ProjectStatus


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None = None
    picture_url: str | None = None


class ProjectImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    ordinal: int

    original_filename: str
    content_type: str
    byte_size: int
    sha256: str
    storage_key: str

    width_px: int | None = None
    height_px: int | None = None

    created_at: datetime


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    page_size: str
    status: ProjectStatus
    latest_job_id: int | None

    created_at: datetime
    updated_at: datetime

    images: list[ProjectImageOut] = []


class ProjectCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    page_size: Literal["16:9", "16:10", "4:3"] = "16:9"


class ProjectUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    page_size: Literal["16:9", "16:10", "4:3"] | None = None


class UploadInitIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    byte_size: int = Field(gt=0)


class UploadInitOut(BaseModel):
    upload_url: str
    storage_key: str


class UploadCompleteIn(BaseModel):
    storage_key: str
    sha256: str | None = None
    width_px: int | None = None
    height_px: int | None = None


class ReorderImagesIn(BaseModel):
    image_ids: list[int]


class JobEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    ts: datetime
    level: EventLevel
    event_type: str
    message: str
    data_json: dict[str, Any] | None = None


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    kind: ArtifactKind
    storage_key: str
    sha256: str
    metadata: dict[str, Any] | None = None
    created_at: datetime

    download_url: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    user_id: int
    status: JobStatus
    step: JobStep
    attempt: int
    idempotency_key: str

    presentation_id: str | None = None
    presentation_url: str | None = None

    error_code: str | None = None
    error_message: str | None = None

    started_at: datetime | None = None
    finished_at: datetime | None = None

    created_at: datetime
    updated_at: datetime

    events: list[JobEventOut] = []
    artifacts: list[ArtifactOut] = []


class GenerateIn(BaseModel):
    page_size: Literal["16:9", "16:10", "4:3"] | None = None
    title: str | None = None


class GenerateOut(BaseModel):
    job_id: int


class OAuthExchangeIn(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] = []
    provider: str = "google"
