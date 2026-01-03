from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func
from typing import List

from database import get_db
from models import User, Project, ProjectImage, Job, JobEvent, JobArtifact, JobStatus, PageSize
from schemas import (
    UserCreate, UserResponse, ProjectCreate, ProjectUpdate, ProjectResponse,
    ProjectListResponse, ImageResponse, JobCreate, JobResponse, JobStatusResponse,
    JobEventResponse, ImageReorderRequest, AuthVerifyResponse
)
from auth import get_or_create_user, get_user_by_id, save_oauth_tokens, get_user_tokens, verify_google_id_token

router = APIRouter(prefix="/api/v1", tags=["api"])


# Health check
@router.get("/health")
async def health_check():
    return {"status": "healthy"}


# Auth endpoints
@router.post("/auth/google", response_model=UserResponse)
async def google_auth(
    id_token: str,
    access_token: str,
    expires_at: int = None,
    db: Session = Depends(get_db)
):
    """Verify Google ID token and create/update user."""
    
    payload = verify_google_id_token(id_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ID token"
        )
    
    google_sub = payload.get("sub")
    email = payload.get("email")
    name = payload.get("name")
    picture_url = payload.get("picture")
    
    user = get_or_create_user(db, google_sub, email, name, picture_url)
    
    # Save OAuth access token
    expires_datetime = None
    if expires_at:
        expires_datetime = datetime.fromtimestamp(expires_at)
    
    save_oauth_tokens(db, user.id, access_token, expires_at=expires_datetime)
    
    return user


@router.get("/me", response_model=AuthVerifyResponse)
async def get_current_user(
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Get current user from authorization header."""
    from auth import verify_access_token, get_user_tokens
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    user = get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Check if user has OAuth tokens with Slides scopes
    tokens = get_user_tokens(db, user.id)
    has_scopes = tokens is not None and tokens.access_token is not None
    
    return AuthVerifyResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        has_slides_scopes=has_scopes
    )


# Project endpoints
@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Create a new project."""
    from auth import verify_access_token, get_user_by_id
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    user = get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    new_project = Project(
        user_id=user.id,
        title=project.title,
        page_size=project.page_size.value
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    
    # Load images relationship
    result = db.execute(
        select(Project)
        .where(Project.id == new_project.id)
        .options(joinedload(Project.images))
    )
    return result.scalar_one()


@router.get("/projects", response_model=List[ProjectListResponse])
async def list_projects(
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """List all projects for current user."""
    from auth import verify_access_token, get_user_by_id
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    
    result = db.execute(
        select(Project)
        .where(Project.user_id == int(user_id))
        .options(joinedload(Project.images))
        .order_by(Project.updated_at.desc())
    )
    projects = result.scalars().all()
    
    return [
        ProjectListResponse(
            id=p.id,
            title=p.title,
            page_size=PageSize(p.page_size),
            created_at=p.created_at,
            updated_at=p.updated_at,
            image_count=len(p.images)
        )
        for p in projects
    ]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Get a specific project with its images."""
    from auth import verify_access_token, get_user_by_id
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    
    result = db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == int(user_id))
        .options(joinedload(Project.images))
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    update: ProjectUpdate,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Update project settings."""
    from auth import verify_access_token, get_user_by_id
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    
    result = db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == int(user_id))
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if update.title:
        project.title = update.title
    if update.page_size:
        project.page_size = update.page_size.value
    
    db.commit()
    db.refresh(project)
    
    # Reload with images
    result = db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(joinedload(Project.images))
    )
    return result.scalar_one()


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Delete a project."""
    from auth import verify_access_token, get_user_by_id
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    
    result = db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == int(user_id))
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    db.delete(project)
    db.commit()


# Image endpoints
@router.post("/projects/{project_id}/images", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def add_image(
    project_id: int,
    original_filename: str,
    storage_path: str,
    ordinal: int,
    width: int = None,
    height: int = None,
    mime_type: str = None,
    file_hash: str = None,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Add an image to a project."""
    from auth import verify_access_token, get_user_by_id
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    
    # Verify project ownership
    result = db.execute(
        select(Project).where(
            Project.id == project_id, 
            Project.user_id == int(user_id)
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Get max ordinal
    result = db.execute(
        select(func.max(ProjectImage.ordinal))
        .where(ProjectImage.project_id == project_id)
    )
    max_ordinal = result.scalar() or 0
    
    image = ProjectImage(
        project_id=project_id,
        original_filename=original_filename,
        storage_path=storage_path,
        ordinal=ordinal if ordinal >= 0 else max_ordinal + 1,
        width=width,
        height=height,
        mime_type=mime_type,
        file_hash=file_hash
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    
    return image


@router.post("/projects/{project_id}/images/reorder")
async def reorder_images(
    project_id: int,
    reorder: ImageReorderRequest,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Reorder images in a project."""
    from auth import verify_access_token, get_user_by_id
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    
    # Verify project ownership
    result = db.execute(
        select(Project).where(
            Project.id == project_id, 
            Project.user_id == int(user_id)
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update ordinals in a transaction
    for ordinal, image_id in enumerate(reorder.image_ids):
        result = db.execute(
            select(ProjectImage)
            .where(ProjectImage.id == image_id, ProjectImage.project_id == project_id)
        )
        image = result.scalar_one_or_none()
        if image:
            image.ordinal = ordinal
    
    db.commit()
    
    # Return updated project
    result = db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(joinedload(Project.images))
    )
    return result.scalar_one()


@router.delete("/projects/{project_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(
    project_id: int,
    image_id: int,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Delete an image from a project."""
    from auth import verify_access_token, get_user_by_id
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    
    # Verify project ownership and get image
    result = db.execute(
        select(ProjectImage)
        .join(Project)
        .where(
            ProjectImage.id == image_id,
            Project.id == project_id,
            Project.user_id == int(user_id)
        )
    )
    image = result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found"
        )
    
    db.delete(image)
    db.commit()


# Job endpoints
@router.post("/projects/{project_id}/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    project_id: int,
    job: JobCreate = None,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Create a new job for a project."""
    from auth import verify_access_token, get_user_by_id
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    
    # Verify project ownership
    result = db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == int(user_id))
        .options(joinedload(Project.images))
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if len(project.images) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project must have at least one image"
        )
    
    # Get page size from project or request
    page_size = job.page_size.value if job and job.page_size else project.page_size
    
    new_job = Job(
        project_id=project_id,
        status=JobStatus.queued,
        page_size=page_size
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    # Load relationships
    result = db.execute(
        select(Job)
        .where(Job.id == new_job.id)
        .options(joinedload(Job.events), joinedload(Job.artifacts))
    )
    return result.scalar_one()


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Get job status and details."""
    from auth import verify_access_token, get_user_by_id
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    
    result = db.execute(
        select(Job)
        .join(Project)
        .where(Job.id == job_id, Project.user_id == int(user_id))
        .options(joinedload(Job.events), joinedload(Job.artifacts))
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job


@router.get("/projects/{project_id}/jobs", response_model=List[JobResponse])
async def list_project_jobs(
    project_id: int,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """List all jobs for a project."""
    from auth import verify_access_token, get_user_by_id
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )
    
    user_id = payload.get("sub")
    
    result = db.execute(
        select(Job)
        .join(Project)
        .where(Project.id == project_id, Project.user_id == int(user_id))
        .options(joinedload(Job.events), joinedload(Job.artifacts))
        .order_by(Job.created_at.desc())
    )
    jobs = result.scalars().all()
    
    return jobs
