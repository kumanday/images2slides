from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from models import JobStatus, PageSize


# User schemas
class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    picture_url: Optional[str] = None


class UserCreate(UserBase):
    google_sub: str


class UserResponse(UserBase):
    id: int
    google_sub: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Project schemas
class ProjectBase(BaseModel):
    title: str
    page_size: PageSize = PageSize.standard_16_9


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    page_size: Optional[PageSize] = None


class ImageBase(BaseModel):
    original_filename: str
    storage_path: str
    ordinal: int
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: Optional[str] = None
    file_hash: Optional[str] = None


class ImageResponse(ImageBase):
    id: int
    project_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectResponse(ProjectBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    images: List[ImageResponse] = []

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    id: int
    title: str
    page_size: PageSize
    created_at: datetime
    updated_at: datetime
    image_count: int

    class Config:
        from_attributes = True


# Job schemas
class JobBase(BaseModel):
    project_id: int
    page_size: Optional[PageSize] = None


class JobCreate(JobBase):
    pass


class JobEventResponse(BaseModel):
    id: int
    job_id: int
    step: str
    status: str
    message: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class JobArtifactResponse(BaseModel):
    id: int
    job_id: int
    artifact_type: str
    name: str
    storage_path: str
    content_hash: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    id: int
    project_id: int
    status: JobStatus
    page_size: Optional[PageSize] = None
    presentation_id: Optional[str] = None
    presentation_url: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    events: List[JobEventResponse] = []
    artifacts: List[JobArtifactResponse] = []

    class Config:
        from_attributes = True


class JobStatusResponse(BaseModel):
    id: int
    status: JobStatus
    presentation_url: Optional[str] = None
    error_message: Optional[str] = None
    events: List[JobEventResponse] = []

    class Config:
        from_attributes = True


# Auth schemas
class TokenPayload(BaseModel):
    sub: str
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    exp: Optional[int] = None


class AuthVerifyResponse(BaseModel):
    user_id: int
    email: str
    name: Optional[str] = None
    has_slides_scopes: bool = False


# Upload schemas
class UploadInitResponse(BaseModel):
    upload_id: str
    presigned_url: str
    fields: dict
    storage_path: str


class ImageReorderRequest(BaseModel):
    image_ids: List[int]
