"""Job pipeline execution."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from saas.backend.db.models import Job, JobEvent, JobArtifact, ProjectImage, OAuthToken, Project
from saas.backend.storage.base import get_storage
from saas.backend.services.encryption import decrypt_token
from saas.backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of pipeline execution."""

    success: bool
    presentation_id: str | None = None
    presentation_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None


async def log_event(
    db: AsyncSession,
    job_id: int,
    event_type: str,
    message: str,
    level: str = "info",
    data: dict | None = None,
) -> None:
    """Log an event for a job."""
    event = JobEvent(
        job_id=job_id,
        level=level,
        event_type=event_type,
        message=message,
        data_json=data,
    )
    db.add(event)
    await db.flush()


async def save_artifact(
    db: AsyncSession,
    job_id: int,
    kind: str,
    data: bytes,
    metadata: dict | None = None,
) -> str:
    """Save an artifact for a job.
    
    Args:
        db: Database session.
        job_id: Job ID.
        kind: Artifact type (e.g., 'raw_layout', 'clean_layout').
        data: Artifact content.
        metadata: Optional metadata.
        
    Returns:
        Storage key of the artifact.
    """
    import hashlib

    sha256 = hashlib.sha256(data).hexdigest()
    storage_key = f"jobs/{job_id}/artifacts/{kind}_{sha256[:12]}.json"

    storage = get_storage()
    await storage.put(storage_key, data, "application/json")

    artifact = JobArtifact(
        job_id=job_id,
        kind=kind,
        storage_key=storage_key,
        sha256=sha256,
        metadata_json=metadata,
    )
    db.add(artifact)
    await db.flush()

    return storage_key


async def update_step(db: AsyncSession, job: Job, step: str, message: str) -> None:
    """Update job step and log event."""
    job.step = step
    await log_event(db, job.id, "step_started", message, data={"step": step})
    await db.commit()


async def get_user_credentials(db: AsyncSession, user_id: int) -> dict | None:
    """Get decrypted OAuth credentials for a user.
    
    Args:
        db: Database session.
        user_id: User ID.
        
    Returns:
        Dict with access_token and refresh_token, or None.
    """
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.user_id == user_id,
            OAuthToken.provider == "google",
        )
    )
    token = result.scalar_one_or_none()

    if not token:
        return None

    return {
        "access_token": decrypt_token(token.access_token_encrypted),
        "refresh_token": (
            decrypt_token(token.refresh_token_encrypted)
            if token.refresh_token_encrypted
            else None
        ),
        "expires_at": token.token_expires_at,
        "scopes": token.scopes or [],
    }


async def run_pipeline(db: AsyncSession, job: Job) -> PipelineResult:
    """Execute the full job pipeline.
    
    Steps:
    1. validate_inputs - Check images exist and user has tokens
    2. extract_layouts - Run VLM to extract layouts from images
    3. postprocess_layouts - Clean and normalize layouts
    4. upload_assets - Upload cropped images (optional)
    5. create_presentation - Create Google Slides presentation
    6. build_slides - Build slides from layouts
    
    Args:
        db: Database session.
        job: Job to process.
        
    Returns:
        PipelineResult with success/failure info.
    """
    try:
        # Load full job with relationships
        result = await db.execute(
            select(Job)
            .where(Job.id == job.id)
            .options(selectinload(Job.artifacts))
        )
        job = result.scalar_one()
        config = job.config_json or {}

        # Step 1: Validate inputs
        await update_step(db, job, "validate_inputs", "Validating inputs...")

        # Get project images
        image_ids = config.get("image_ids", [])
        if not image_ids:
            return PipelineResult(
                success=False,
                error_code="NO_IMAGES",
                error_message="No images in project",
            )

        images_result = await db.execute(
            select(ProjectImage)
            .where(ProjectImage.id.in_(image_ids))
            .order_by(ProjectImage.ordinal)
        )
        images = images_result.scalars().all()

        if len(images) != len(image_ids):
            return PipelineResult(
                success=False,
                error_code="MISSING_IMAGES",
                error_message=f"Expected {len(image_ids)} images, found {len(images)}",
            )

        # Check user credentials
        credentials = await get_user_credentials(db, job.user_id)
        if not credentials:
            return PipelineResult(
                success=False,
                error_code="NO_CREDENTIALS",
                error_message="User has not granted Google permissions",
            )

        # Check for required scopes
        required_scopes = {
            "https://www.googleapis.com/auth/presentations",
            "https://www.googleapis.com/auth/drive.file",
        }
        user_scopes = set(credentials.get("scopes", []))
        if not required_scopes.issubset(user_scopes):
            missing = required_scopes - user_scopes
            return PipelineResult(
                success=False,
                error_code="MISSING_SCOPES",
                error_message=f"Missing required scopes: {missing}",
            )

        await log_event(
            db, job.id, "validation_complete",
            f"Validated {len(images)} images and user credentials",
        )

        # Step 2: Extract layouts using VLM
        await update_step(db, job, "extract_layouts", "Extracting layouts from images...")

        storage = get_storage()
        layouts = []
        raw_layouts = []

        for i, image in enumerate(images):
            await log_event(
                db, job.id, "extracting_image",
                f"Processing image {i + 1}/{len(images)}: {image.original_filename}",
                data={"image_id": image.id, "storage_key": image.storage_key},
            )

            # Download image to temp file
            image_data = await storage.get(image.storage_key)
            temp_path = Path(f"/tmp/job_{job.id}_image_{image.id}.png")
            temp_path.write_bytes(image_data)

            try:
                # Import the upstream extraction function
                from images2slides.vlm.extract import extract_layout_from_image, VLMConfig

                vlm_config = VLMConfig(
                    provider=settings.vlm_provider,
                    model=settings.vlm_model,
                )

                layout = extract_layout_from_image(temp_path, vlm_config)
                raw_layout_dict = layout.to_dict()
                raw_layouts.append(raw_layout_dict)

                # Save raw layout artifact
                await save_artifact(
                    db, job.id, f"raw_layout_{i}",
                    json.dumps(raw_layout_dict, indent=2).encode(),
                    metadata={"image_id": image.id, "index": i},
                )

                layouts.append(layout)

            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()

        await log_event(
            db, job.id, "extraction_complete",
            f"Extracted layouts from {len(layouts)} images",
        )

        # Step 3: Postprocess layouts
        await update_step(db, job, "postprocess_layouts", "Post-processing layouts...")

        from images2slides.postprocess import postprocess_layout

        clean_layouts = []
        for i, layout in enumerate(layouts):
            clean_layout = postprocess_layout(layout)
            clean_layouts.append(clean_layout)

            # Save clean layout artifact
            await save_artifact(
                db, job.id, f"clean_layout_{i}",
                json.dumps(clean_layout.to_dict(), indent=2).encode(),
                metadata={"index": i},
            )

        await log_event(
            db, job.id, "postprocess_complete",
            f"Post-processed {len(clean_layouts)} layouts",
        )

        # Step 4: Upload assets (skip for MVP - text-only reconstruction)
        await update_step(db, job, "upload_assets", "Preparing assets...")
        await log_event(
            db, job.id, "assets_skipped",
            "Skipping image region uploads (text-only mode)",
        )

        # Step 5 & 6: Create presentation and build slides
        await update_step(db, job, "create_presentation", "Creating Google Slides presentation...")

        # Build credentials for Google API
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=credentials["access_token"],
            refresh_token=credentials.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )

        slides_service = build("slides", "v1", credentials=creds)

        # Import slide building functions
        from images2slides.build_slide import build_presentation_from_layouts

        # Map page size to preset
        page_size = config.get("page_size", "16:9")
        page_size_presets = {
            "16:9": "WIDESCREEN_16_9",
            "16:10": "WIDESCREEN_16_10",
            "4:3": "STANDARD_4_3",
        }
        preset = page_size_presets.get(page_size, "WIDESCREEN_16_9")

        title = config.get("title", "Infographic Presentation")

        await log_event(
            db, job.id, "building_presentation",
            f"Building presentation: {title} ({page_size})",
            data={"title": title, "page_size": page_size, "num_slides": len(clean_layouts)},
        )

        # Build the presentation
        result = build_presentation_from_layouts(
            service=slides_service,
            layouts=clean_layouts,
            title=title,
            page_size=preset,
            place_backgrounds=False,  # No backgrounds for text-only mode
        )

        # Save run config artifact
        await save_artifact(
            db, job.id, "run_config",
            json.dumps({
                "title": title,
                "page_size": page_size,
                "vlm_provider": settings.vlm_provider,
                "vlm_model": settings.vlm_model,
                "num_images": len(images),
                "presentation_id": result.presentation_id,
                "presentation_url": result.presentation_url,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2).encode(),
        )

        await log_event(
            db, job.id, "presentation_created",
            f"Created presentation with {result.num_slides} slides",
            data={
                "presentation_id": result.presentation_id,
                "presentation_url": result.presentation_url,
            },
        )

        return PipelineResult(
            success=True,
            presentation_id=result.presentation_id,
            presentation_url=result.presentation_url,
        )

    except Exception as e:
        logger.exception(f"Pipeline error for job {job.id}")
        await log_event(
            db, job.id, "pipeline_error",
            f"Pipeline failed: {e}",
            level="error",
            data={"error": str(e), "error_type": type(e).__name__},
        )
        return PipelineResult(
            success=False,
            error_code="PIPELINE_ERROR",
            error_message=str(e),
        )