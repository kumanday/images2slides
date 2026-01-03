from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
import hashlib
import shutil
from PIL import Image
from saas.api.database import get_db
from saas.api.models import User, Project, ProjectImage
from saas.api.routers.auth import get_current_user

router = APIRouter()


class ProjectImageResponse(BaseModel):
    id: int
    project_id: int
    original_filename: str
    storage_path: str
    ordinal: int
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: Optional[str] = None
    file_hash: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    title: str
    page_size: str = "STANDARD_4_3"


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    page_size: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    user_id: int
    title: str
    page_size: str
    created_at: datetime
    updated_at: datetime
    images: List[ProjectImageResponse] = []

    class Config:
        from_attributes = True


# Allowed image MIME types
ALLOWED_MIME_TYPES = ["image/png", "image/jpeg", "image/webp"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_IMAGES_PER_PROJECT = 20


def get_storage_path(project_id: int, filename: str) -> str:
    """Generate storage path for an uploaded image"""
    # Create uploads directory if it doesn't exist
    uploads_dir = os.path.join("uploads", str(project_id))
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(filename)
    unique_filename = f"{timestamp}_{name}{ext}"
    
    return os.path.join(uploads_dir, unique_filename)


def calculate_file_hash(filepath: str) -> str:
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_image_dimensions(filepath: str) -> tuple[int, int]:
    """Get image dimensions"""
    with Image.open(filepath) as img:
        return img.size


@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new project"""
    new_project = Project(
        user_id=current_user.id,
        title=project.title,
        page_size=project.page_size
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    
    return new_project


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all projects for current user"""
    projects = db.query(Project).filter(
        Project.user_id == current_user.id
    ).order_by(Project.updated_at.desc()).all()
    
    return projects


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a project"""
    db_project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.title is not None:
        db_project.title = project.title
    if project.page_size is not None:
        db_project.page_size = project.page_size
    
    db.commit()
    db.refresh(db_project)
    
    return db_project


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete uploaded files
    uploads_dir = os.path.join("uploads", str(project_id))
    if os.path.exists(uploads_dir):
        shutil.rmtree(uploads_dir)
    
    db.delete(project)
    db.commit()
    
    return {"message": "Project deleted"}


@router.post("/projects/{project_id}/images", response_model=ProjectImageResponse)
async def upload_image(
    project_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload an image to a project"""
    # Verify project ownership
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    
    # Check image count limit
    image_count = db.query(ProjectImage).filter(
        ProjectImage.project_id == project_id
    ).count()
    
    if image_count >= MAX_IMAGES_PER_PROJECT:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_IMAGES_PER_PROJECT} images per project"
        )
    
    # Read file content
    content = await file.read()
    
    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    # Save file
    storage_path = get_storage_path(project_id, file.filename)
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    
    with open(storage_path, "wb") as f:
        f.write(content)
    
    # Get image metadata
    width, height = get_image_dimensions(storage_path)
    file_hash = calculate_file_hash(storage_path)
    
    # Get next ordinal
    max_ordinal = db.query(ProjectImage).filter(
        ProjectImage.project_id == project_id
    ).count()
    
    # Create database record
    new_image = ProjectImage(
        project_id=project_id,
        original_filename=file.filename,
        storage_path=storage_path,
        ordinal=max_ordinal + 1,
        width=width,
        height=height,
        mime_type=file.content_type,
        file_hash=file_hash
    )
    db.add(new_image)
    db.commit()
    db.refresh(new_image)
    
    return new_image


@router.put("/projects/{project_id}/images/reorder")
async def reorder_images(
    project_id: int,
    image_ids: List[int],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reorder images in a project"""
    # Verify project ownership
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Verify all images belong to this project
    images = db.query(ProjectImage).filter(
        ProjectImage.project_id == project_id,
        ProjectImage.id.in_(image_ids)
    ).all()
    
    if len(images) != len(image_ids):
        raise HTTPException(status_code=400, detail="Some images not found in project")
    
    # Update ordinals transactionally
    for ordinal, image_id in enumerate(image_ids, start=1):
        image = next((img for img in images if img.id == image_id), None)
        if image:
            image.ordinal = ordinal
    
    db.commit()
    
    return {"message": "Images reordered"}


@router.delete("/projects/{project_id}/images/{image_id}")
async def delete_image(
    project_id: int,
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an image from a project"""
    # Verify project ownership
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get image
    image = db.query(ProjectImage).filter(
        ProjectImage.id == image_id,
        ProjectImage.project_id == project_id
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Delete file
    if os.path.exists(image.storage_path):
        os.remove(image.storage_path)
    
    # Delete database record
    db.delete(image)
    
    # Reorder remaining images
    remaining_images = db.query(ProjectImage).filter(
        ProjectImage.project_id == project_id
    ).order_by(ProjectImage.ordinal).all()
    
    for ordinal, img in enumerate(remaining_images, start=1):
        img.ordinal = ordinal
    
    db.commit()
    
    return {"message": "Image deleted"}
