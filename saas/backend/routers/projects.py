"""Project management endpoints."""

import hashlib
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.session import get_db
from ..db.models import User, Project, ProjectImage, Job
from ..services.auth import get_current_user
from ..storage.base import get_storage
from ..config import settings

router = APIRouter()

PageSize = Literal["16:9", "16:10", "4:3"]


class ProjectCreate(BaseModel):
    """Request to create a project."""

    title: str
    page_size: PageSize = "16:9"


class ProjectUpdate(BaseModel):
    """Request to update a project."""

    title: str | None = None
    page_size: PageSize | None = None


class ProjectImageResponse(BaseModel):
    """Project image response."""

    id: int
    project_id: int
    ordinal: int
    original_filename: str
    content_type: str
    byte_size: int
    sha256: str
    storage_key: str
    width_px: int | None
    height_px: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    """Project response with images."""

    id: int
    user_id: int
    title: str
    page_size: str
    status: str
    latest_job_id: int | None
    created_at: datetime
    updated_at: datetime
    images: list[ProjectImageResponse]

    class Config:
        from_attributes = True


class UploadInitRequest(BaseModel):
    """Request to initialize an upload."""

    filename: str
    content_type: str
    byte_size: int


class UploadInitResponse(BaseModel):
    """Response with presigned upload URL."""

    upload_url: str
    storage_key: str


class UploadCompleteRequest(BaseModel):
    """Request to complete an upload."""

    storage_key: str


class ReorderImagesRequest(BaseModel):
    """Request to reorder images."""

    image_ids: list[int]


class GenerateRequest(BaseModel):
    """Request to generate slides."""

    page_size: PageSize | None = None


class GenerateResponse(BaseModel):
    """Response with job ID."""

    job_id: int


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponse:
    """Create a new project.
    
    Args:
        request: Project creation data.
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        Created project.
    """
    project = Project(
        user_id=current_user.id,
        title=request.title,
        page_size=request.page_size,
        status="draft",
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        title=project.title,
        page_size=project.page_size,
        status=project.status,
        latest_job_id=project.latest_job_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        images=[],
    )


@router.get("/projects")
async def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProjectResponse]:
    """List all projects for the current user.
    
    Args:
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        List of projects with images.
    """
    result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .options(selectinload(Project.images))
        .order_by(Project.updated_at.desc())
    )
    projects = result.scalars().all()

    return [
        ProjectResponse(
            id=p.id,
            user_id=p.user_id,
            title=p.title,
            page_size=p.page_size,
            status=p.status,
            latest_job_id=p.latest_job_id,
            created_at=p.created_at,
            updated_at=p.updated_at,
            images=[ProjectImageResponse.model_validate(img) for img in p.images],
        )
        for p in projects
    ]


@router.get("/projects/{project_id}")
async def get_project(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponse:
    """Get a specific project.
    
    Args:
        project_id: Project ID.
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        Project with images.
        
    Raises:
        HTTPException: If project not found or not owned by user.
    """
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == current_user.id)
        .options(selectinload(Project.images))
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        title=project.title,
        page_size=project.page_size,
        status=project.status,
        latest_job_id=project.latest_job_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        images=[ProjectImageResponse.model_validate(img) for img in project.images],
    )


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: int,
    request: ProjectUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponse:
    """Update a project.
    
    Args:
        project_id: Project ID.
        request: Update data.
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        Updated project.
        
    Raises:
        HTTPException: If project not found.
    """
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == current_user.id)
        .options(selectinload(Project.images))
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.title is not None:
        project.title = request.title
    if request.page_size is not None:
        project.page_size = request.page_size

    await db.flush()

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        title=project.title,
        page_size=project.page_size,
        status=project.status,
        latest_job_id=project.latest_job_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        images=[ProjectImageResponse.model_validate(img) for img in project.images],
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a project.
    
    Args:
        project_id: Project ID.
        current_user: Authenticated user.
        db: Database session.
        
    Raises:
        HTTPException: If project not found.
    """
    result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)


@router.post("/projects/{project_id}/uploads/init")
async def init_upload(
    project_id: int,
    request: UploadInitRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadInitResponse:
    """Initialize an image upload.
    
    Returns a presigned URL for direct upload to storage.
    
    Args:
        project_id: Project ID.
        request: Upload metadata.
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        Upload URL and storage key.
        
    Raises:
        HTTPException: If project not found or limits exceeded.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check limits
    if request.byte_size > settings.max_image_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {settings.max_image_size_bytes} bytes",
        )

    # Validate content type
    allowed_types = {"image/png", "image/jpeg", "image/webp"}
    if request.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type. Allowed: {allowed_types}",
        )

    # Check image count
    count_result = await db.execute(
        select(func.count(ProjectImage.id)).where(
            ProjectImage.project_id == project_id
        )
    )
    image_count = count_result.scalar() or 0
    if image_count >= settings.max_images_per_project:
        raise HTTPException(
            status_code=400,
            detail=f"Max images per project: {settings.max_images_per_project}",
        )

    # Generate storage key
    unique_id = uuid.uuid4().hex[:12]
    ext = request.filename.rsplit(".", 1)[-1] if "." in request.filename else "bin"
    storage_key = f"projects/{project_id}/uploads/{unique_id}.{ext}"

    # Get presigned URL
    storage = get_storage()
    upload_url = await storage.get_upload_url(
        storage_key, request.content_type, expires_in=3600
    )

    return UploadInitResponse(upload_url=upload_url, storage_key=storage_key)


@router.post("/projects/{project_id}/uploads/complete")
async def complete_upload(
    project_id: int,
    request: UploadCompleteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectImageResponse:
    """Complete an image upload and create the image record.
    
    Args:
        project_id: Project ID.
        request: Storage key of uploaded file.
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        Created image record.
        
    Raises:
        HTTPException: If project not found or upload failed.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify file exists and get metadata
    storage = get_storage()
    try:
        metadata = await storage.get_metadata(request.storage_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Upload verification failed: {e}")

    # Get next ordinal
    count_result = await db.execute(
        select(func.count(ProjectImage.id)).where(
            ProjectImage.project_id == project_id
        )
    )
    next_ordinal = (count_result.scalar() or 0) + 1

    # Extract filename from storage key
    filename = request.storage_key.rsplit("/", 1)[-1]

    # Create image record
    image = ProjectImage(
        project_id=project_id,
        ordinal=next_ordinal,
        original_filename=filename,
        content_type=metadata.get("content_type", "image/png"),
        byte_size=metadata.get("size", 0),
        sha256=metadata.get("sha256", ""),
        storage_key=request.storage_key,
        width_px=metadata.get("width"),
        height_px=metadata.get("height"),
    )
    db.add(image)
    await db.flush()
    await db.refresh(image)

    return ProjectImageResponse.model_validate(image)


@router.patch("/projects/{project_id}/images/reorder")
async def reorder_images(
    project_id: int,
    request: ReorderImagesRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProjectImageResponse]:
    """Reorder images within a project.
    
    Args:
        project_id: Project ID.
        request: New order of image IDs.
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        Updated list of images in new order.
        
    Raises:
        HTTPException: If project not found or invalid image IDs.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == current_user.id)
        .options(selectinload(Project.images))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate all image IDs belong to this project
    existing_ids = {img.id for img in project.images}
    requested_ids = set(request.image_ids)
    if existing_ids != requested_ids:
        raise HTTPException(
            status_code=400,
            detail="Image IDs must match exactly the images in this project",
        )

    # Update ordinals
    id_to_image = {img.id: img for img in project.images}
    for ordinal, image_id in enumerate(request.image_ids, start=1):
        id_to_image[image_id].ordinal = ordinal

    await db.flush()

    # Return reordered images
    sorted_images = sorted(project.images, key=lambda x: x.ordinal)
    return [ProjectImageResponse.model_validate(img) for img in sorted_images]


@router.delete(
    "/projects/{project_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_image(
    project_id: int,
    image_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete an image from a project.
    
    Args:
        project_id: Project ID.
        image_id: Image ID.
        current_user: Authenticated user.
        db: Database session.
        
    Raises:
        HTTPException: If project or image not found.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == current_user.id)
        .options(selectinload(Project.images))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Find and delete image
    image_to_delete = None
    for img in project.images:
        if img.id == image_id:
            image_to_delete = img
            break

    if not image_to_delete:
        raise HTTPException(status_code=404, detail="Image not found")

    await db.delete(image_to_delete)

    # Recompact ordinals
    remaining = [img for img in project.images if img.id != image_id]
    remaining.sort(key=lambda x: x.ordinal)
    for i, img in enumerate(remaining, start=1):
        img.ordinal = i


@router.post("/projects/{project_id}/generate")
async def generate_slides(
    project_id: int,
    request: GenerateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GenerateResponse:
    """Start a slide generation job for a project.
    
    Args:
        project_id: Project ID.
        request: Generation options.
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        Job ID for tracking.
        
    Raises:
        HTTPException: If project not found or has no images.
    """
    # Verify project ownership and load images
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == current_user.id)
        .options(selectinload(Project.images))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.images:
        raise HTTPException(status_code=400, detail="Project has no images")

    # Update page size if provided
    if request.page_size:
        project.page_size = request.page_size

    # Create job with unique idempotency key
    idempotency_key = f"{project_id}-{uuid.uuid4().hex[:8]}"
    job = Job(
        project_id=project_id,
        user_id=current_user.id,
        status="queued",
        step="pending",
        attempt=1,
        idempotency_key=idempotency_key,
        config_json={
            "page_size": project.page_size,
            "title": project.title,
            "image_ids": [img.id for img in sorted(project.images, key=lambda x: x.ordinal)],
        },
    )
    db.add(job)
    await db.flush()

    # Update project's latest job
    project.latest_job_id = job.id

    await db.refresh(job)

    return GenerateResponse(job_id=job.id)