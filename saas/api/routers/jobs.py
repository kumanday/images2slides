from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from saas.api.database import get_db
from saas.api.models import User, Job, JobEvent, JobArtifact, JobStatus
from saas.api.routers.auth import get_current_user

router = APIRouter()


class JobEventResponse(BaseModel):
    id: int
    job_id: int
    step: str
    status: str
    message: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class JobArtifactResponse(BaseModel):
    id: int
    job_id: int
    artifact_type: str
    name: str
    storage_path: str
    content_hash: Optional[str] = None
    metadata: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    id: int
    project_id: int
    status: JobStatus
    page_size: Optional[str] = None
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


class CreateJobRequest(BaseModel):
    page_size: Optional[str] = None


@router.post("/projects/{project_id}/jobs", response_model=JobResponse)
async def create_job(
    project_id: int,
    request: CreateJobRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new job to generate slides"""
    from saas.api.models import Project
    
    # Verify project ownership
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if project has images
    if not project.images:
        raise HTTPException(status_code=400, detail="Project has no images")
    
    # Check if there's a running job
    running_job = db.query(Job).filter(
        Job.project_id == project_id,
        Job.status.in_([JobStatus.queued, JobStatus.running])
    ).first()
    
    if running_job:
        raise HTTPException(
            status_code=400,
            detail=f"A job is already {running_job.status.value} for this project"
        )
    
    # Create job
    new_job = Job(
        project_id=project_id,
        status=JobStatus.queued,
        page_size=request.page_size or project.page_size,
        retry_count=0
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    return new_job


@router.get("/projects/{project_id}/jobs", response_model=List[JobResponse])
async def list_jobs(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all jobs for a project"""
    from saas.api.models import Project
    
    # Verify project ownership
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    jobs = db.query(Job).filter(
        Job.project_id == project_id
    ).order_by(Job.created_at.desc()).all()
    
    return jobs


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific job"""
    from saas.api.models import Project
    
    # Get job with project
    job = db.query(Job).join(Project).filter(
        Job.id == job_id,
        Project.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retry a failed job"""
    from saas.api.models import Project
    
    # Get job with project
    job = db.query(Job).join(Project).filter(
        Job.id == job_id,
        Project.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Only allow retrying failed jobs
    if job.status != JobStatus.failed:
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed jobs. Current status: {job.status.value}"
        )
    
    # Check retry count
    MAX_RETRIES = 3
    if job.retry_count >= MAX_RETRIES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum retry count ({MAX_RETRIES}) exceeded"
        )
    
    # Check if there's a running job for this project
    running_job = db.query(Job).filter(
        Job.project_id == job.project_id,
        Job.status.in_([JobStatus.queued, JobStatus.running]),
        Job.id != job_id
    ).first()
    
    if running_job:
        raise HTTPException(
            status_code=400,
            detail=f"A job is already {running_job.status.value} for this project"
        )
    
    # Create new job for retry
    new_job = Job(
        project_id=job.project_id,
        status=JobStatus.queued,
        page_size=job.page_size,
        retry_count=job.retry_count + 1
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    return new_job
