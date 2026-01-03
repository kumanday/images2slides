"""Job management endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.session import get_db
from ..db.models import User, Job, JobEvent, JobArtifact, Project
from ..services.auth import get_current_user
from ..storage.base import get_storage

router = APIRouter()


class JobEventResponse(BaseModel):
    """Job event response."""

    id: int
    job_id: int
    ts: datetime
    level: str
    event_type: str
    message: str
    data_json: dict | None

    class Config:
        from_attributes = True


class JobArtifactResponse(BaseModel):
    """Job artifact response."""

    id: int
    job_id: int
    kind: str
    storage_key: str
    sha256: str
    metadata: dict | None
    created_at: datetime
    download_url: str | None = None

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    """Job response with events and artifacts."""

    id: int
    project_id: int
    user_id: int
    status: str
    step: str
    attempt: int
    idempotency_key: str
    presentation_id: str | None
    presentation_url: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    events: list[JobEventResponse]
    artifacts: list[JobArtifactResponse]

    class Config:
        from_attributes = True


class RetryResponse(BaseModel):
    """Response after retrying a job."""

    job_id: int


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobResponse:
    """Get a specific job.
    
    Args:
        job_id: Job ID.
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        Job with events and artifacts.
        
    Raises:
        HTTPException: If job not found or not owned by user.
    """
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id, Job.user_id == current_user.id)
        .options(selectinload(Job.events), selectinload(Job.artifacts))
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        id=job.id,
        project_id=job.project_id,
        user_id=job.user_id,
        status=job.status,
        step=job.step,
        attempt=job.attempt,
        idempotency_key=job.idempotency_key,
        presentation_id=job.presentation_id,
        presentation_url=job.presentation_url,
        error_code=job.error_code,
        error_message=job.error_message,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        events=[
            JobEventResponse(
                id=e.id,
                job_id=e.job_id,
                ts=e.ts,
                level=e.level,
                event_type=e.event_type,
                message=e.message,
                data_json=e.data_json,
            )
            for e in job.events
        ],
        artifacts=[
            JobArtifactResponse(
                id=a.id,
                job_id=a.job_id,
                kind=a.kind,
                storage_key=a.storage_key,
                sha256=a.sha256,
                metadata=a.metadata_json,
                created_at=a.created_at,
            )
            for a in job.artifacts
        ],
    )


@router.get("/jobs/{job_id}/artifacts")
async def get_job_artifacts(
    job_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[JobArtifactResponse]:
    """Get artifacts for a job with download URLs.
    
    Args:
        job_id: Job ID.
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        List of artifacts with download URLs.
        
    Raises:
        HTTPException: If job not found.
    """
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id, Job.user_id == current_user.id)
        .options(selectinload(Job.artifacts))
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    storage = get_storage()
    artifacts = []

    for a in job.artifacts:
        download_url = await storage.get_download_url(a.storage_key, expires_in=3600)
        artifacts.append(
            JobArtifactResponse(
                id=a.id,
                job_id=a.job_id,
                kind=a.kind,
                storage_key=a.storage_key,
                sha256=a.sha256,
                metadata=a.metadata_json,
                created_at=a.created_at,
                download_url=download_url,
            )
        )

    return artifacts


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetryResponse:
    """Create a new job to retry a failed job.
    
    This creates a new job with the same configuration.
    The original job is not modified.
    
    Args:
        job_id: Original job ID.
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        New job ID.
        
    Raises:
        HTTPException: If job not found or cannot be retried.
    """
    import uuid

    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    original_job = result.scalar_one_or_none()

    if not original_job:
        raise HTTPException(status_code=404, detail="Job not found")

    if original_job.status not in ("failed", "canceled"):
        raise HTTPException(
            status_code=400,
            detail="Can only retry failed or canceled jobs",
        )

    # Create new job with same config
    new_idempotency_key = f"{original_job.project_id}-{uuid.uuid4().hex[:8]}"
    new_job = Job(
        project_id=original_job.project_id,
        user_id=current_user.id,
        status="queued",
        step="pending",
        attempt=original_job.attempt + 1,
        idempotency_key=new_idempotency_key,
        config_json=original_job.config_json,
    )
    db.add(new_job)
    await db.flush()

    # Update project's latest job
    project_result = await db.execute(
        select(Project).where(Project.id == original_job.project_id)
    )
    project = project_result.scalar_one_or_none()
    if project:
        project.latest_job_id = new_job.id

    await db.refresh(new_job)

    return RetryResponse(job_id=new_job.id)