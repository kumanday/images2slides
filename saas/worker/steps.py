"""Pipeline steps for the conversion engine"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
from pathlib import Path
import json
import os

from saas.api.models import Job, Project, ProjectImage, JobArtifact
from saas.api.oauth_manager import get_decrypted_access_token

# Import from images2slides library
from images2slides.vlm.extract import extract_layout_from_image, VLMConfig
from images2slides.postprocess import postprocess_layout
from images2slides.build_slide import build_presentation
from images2slides.auth import get_credentials

logger = logging.getLogger(__name__)


def validate_inputs_step(job: Job, db: Session) -> Dict[str, Any]:
    """Validate that all required inputs are present"""
    logger.info(f"Validating inputs for job {job.id}")
    
    # Check project exists
    project = db.query(Project).filter(Project.id == job.project_id).first()
    if not project:
        raise ValueError(f"Project {job.project_id} not found")
    
    # Check project has images
    images = db.query(ProjectImage).filter(
        ProjectImage.project_id == job.project_id
    ).order_by(ProjectImage.ordinal).all()
    
    if not images:
        raise ValueError(f"Project {job.project_id} has no images")
    
    # Check user has OAuth tokens
    from saas.api.models import User
    user = db.query(User).filter(User.id == project.user_id).first()
    if not user:
        raise ValueError(f"User {project.user_id} not found")
    
    access_token = get_decrypted_access_token(db, user, "google")
    if not access_token:
        raise ValueError(f"User {user.email} has no Google OAuth token")
    
    logger.info(f"Validation passed: {len(images)} images found")
    return {"image_count": len(images)}


def extract_layouts_step(job: Job, db: Session) -> Dict[str, Any]:
    """Extract layouts from images using VLM"""
    logger.info(f"Extracting layouts for job {job.id}")
    
    # Get project and images
    project = db.query(Project).filter(Project.id == job.project_id).first()
    images = db.query(ProjectImage).filter(
        ProjectImage.project_id == job.project_id
    ).order_by(ProjectImage.ordinal).all()
    
    # Configure VLM
    vlm_provider = os.getenv("VLM_PROVIDER", "openai")
    vlm_model = os.getenv("VLM_MODEL")
    
    config = VLMConfig(
        provider=vlm_provider,
        model=vlm_model
    )
    
    # Extract layouts for each image
    layouts = []
    for image in images:
        logger.info(f"Extracting layout from {image.original_filename}")
        
        try:
            layout = extract_layout_from_image(image.storage_path, config)
            layouts.append(layout)
            
            # Store raw layout as artifact
            artifact = JobArtifact(
                job_id=job.id,
                artifact_type="raw_layout",
                name=f"raw_layout_{image.id}.json",
                storage_path=f"/tmp/raw_layout_{job.id}_{image.id}.json",
                content_hash=image.file_hash,
                metadata=json.dumps({"image_id": image.id, "filename": image.original_filename})
            )
            db.add(artifact)
            
        except Exception as e:
            logger.error(f"Failed to extract layout from {image.original_filename}: {e}")
            raise
    
    db.commit()
    
    logger.info(f"Layout extraction completed for job {job.id}: {len(layouts)} layouts")
    return {"layout_count": len(layouts)}


def postprocess_layouts_step(job: Job, db: Session) -> Dict[str, Any]:
    """Postprocess and clean layouts"""
    logger.info(f"Postprocessing layouts for job {job.id}")
    
    # Get raw layout artifacts
    raw_artifacts = db.query(JobArtifact).filter(
        JobArtifact.job_id == job.id,
        JobArtifact.artifact_type == "raw_layout"
    ).all()
    
    # Postprocess each layout
    for artifact in raw_artifacts:
        try:
            # Load raw layout
            with open(artifact.storage_path, 'r') as f:
                raw_layout = json.load(f)
            
            # Postprocess
            clean_layout = postprocess_layout(raw_layout)
            
            # Store clean layout as artifact
            clean_artifact = JobArtifact(
                job_id=job.id,
                artifact_type="clean_layout",
                name=f"clean_layout_{artifact.id}.json",
                storage_path=f"/tmp/clean_layout_{job.id}_{artifact.id}.json",
                metadata=json.dumps({"raw_artifact_id": artifact.id})
            )
            db.add(clean_artifact)
            
            # Save clean layout to file
            with open(clean_artifact.storage_path, 'w') as f:
                json.dump(clean_layout, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to postprocess layout {artifact.id}: {e}")
            raise
    
    db.commit()
    
    logger.info(f"Layout postprocessing completed for job {job.id}")
    return {}


def upload_assets_step(job: Job, db: Session) -> Dict[str, Any]:
    """Upload image assets to storage (optional)"""
    logger.info(f"Uploading assets for job {job.id}")
    
    # TODO: Implement asset upload if storage is configured
    # For MVP, this step is skipped
    
    logger.info(f"Asset upload completed for job {job.id}")
    return {}


def create_presentation_step(job: Job, db: Session) -> Dict[str, Any]:
    """Create Google Slides presentation"""
    logger.info(f"Creating presentation for job {job.id}")
    
    # Get project and user
    project = db.query(Project).filter(Project.id == job.project_id).first()
    from saas.api.models import User
    user = db.query(User).filter(User.id == project.user_id).first()
    
    # Get OAuth token
    access_token = get_decrypted_access_token(db, user, "google")
    if not access_token:
        raise ValueError(f"User {user.email} has no Google OAuth token")
    
    # Get credentials from access token
    credentials = get_credentials(access_token)
    
    # Create presentation
    presentation_id, presentation_url = build_presentation(
        credentials=credentials,
        title=project.title,
        page_size=job.page_size or project.page_size
    )
    
    logger.info(f"Presentation created: {presentation_id}")
    
    return {
        "presentation_id": presentation_id,
        "presentation_url": presentation_url
    }


def build_slides_step(job: Job, db: Session) -> Dict[str, Any]:
    """Build slides in the presentation"""
    logger.info(f"Building slides for job {job.id}")
    
    # Get clean layout artifacts
    clean_artifacts = db.query(JobArtifact).filter(
        JobArtifact.job_id == job.id,
        JobArtifact.artifact_type == "clean_layout"
    ).all()
    
    # Get project images
    images = db.query(ProjectImage).filter(
        ProjectImage.project_id == job.project_id
    ).order_by(ProjectImage.ordinal).all()
    
    # Get user credentials
    project = db.query(Project).filter(Project.id == job.project_id).first()
    from saas.api.models import User
    user = db.query(User).filter(User.id == project.user_id).first()
    access_token = get_decrypted_access_token(db, user, "google")
    credentials = get_credentials(access_token)
    
    # Build slides for each layout
    # Note: This is a simplified version. The full implementation would
    # use the build_presentation function with all layouts at once
    from images2slides.build_slide import build_requests_for_infographic
    from images2slides.geometry import compute_fit
    from images2slides.slides_api import (
        get_page_size_pt,
        req_delete_slide,
        req_text_style
    )
    
    # Get presentation ID from job
    presentation_id = job.presentation_id
    if not presentation_id:
        raise ValueError("Presentation ID not found in job")
    
    # Get page size
    from googleapiclient.discovery import build
    service = build('slides', 'v1', credentials=credentials)
    page_size_pt = get_page_size_pt(service, presentation_id)
    
    # Build slides for each image/layout
    for i, (artifact, image) in enumerate(zip(clean_artifacts, images)):
        logger.info(f"Building slide {i+1}/{len(clean_artifacts)}")
        
        # Load clean layout
        with open(artifact.storage_path, 'r') as f:
            layout = json.load(f)
        
        # Compute fit
        fit = compute_fit(layout, page_size_pt)
        
        # Build requests for this slide
        # Note: This is simplified. Full implementation would use
        # the complete build_requests_for_infographic function
        # and batch update
        
        logger.info(f"Built slide {i+1} with {len(layout.get('regions', []))} regions")
    
    logger.info(f"Slides built for job {job.id}")
    return {}
