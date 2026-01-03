from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.models import PendingUpload, Project, ProjectImage, ProjectStatus, User
from ..db.session import get_db
from ..schemas import (
    ProjectImageOut,
    ReorderImagesIn,
    UploadCompleteIn,
    UploadInitIn,
    UploadInitOut,
)
from ..services.auth import get_current_user
from ..services.upload_signing import UploadTokenPayload, sign_upload_token, verify_upload_token
from ..storage import get_upload_storage

router = APIRouter()


def _get_project(db: Session, user_id: int, project_id: int) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
            Project.status != ProjectStatus.archived,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/projects/{project_id}/uploads/init", response_model=UploadInitOut)
def upload_init(
    project_id: int,
    body: UploadInitIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadInitOut:
    settings = get_settings()
    _get_project(db, user.id, project_id)

    if body.byte_size > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    safe_name = os.path.basename(body.filename)
    storage_key = f"u{user.id}/p{project_id}/{uuid.uuid4().hex}_{safe_name}"

    expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=15)
    pending = PendingUpload(
        project_id=project_id,
        user_id=user.id,
        storage_key=storage_key,
        original_filename=safe_name,
        content_type=body.content_type,
        byte_size=body.byte_size,
        expires_at=expires_at,
    )
    db.add(pending)
    db.commit()

    token = sign_upload_token(
        UploadTokenPayload(
            storage_key=storage_key,
            user_id=user.id,
            project_id=project_id,
            exp=int(expires_at.timestamp()),
        )
    )

    upload_url = f"{settings.api_base_url}/api/v1/uploads/{storage_key}?token={token}"
    return UploadInitOut(upload_url=upload_url, storage_key=storage_key)


@router.put("/uploads/{storage_key:path}")
async def upload_put(
    storage_key: str,
    request: Request,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    settings = get_settings()

    try:
        payload = verify_upload_token(token)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid upload token") from e

    if payload.storage_key != storage_key:
        raise HTTPException(status_code=401, detail="Invalid upload token")

    pending = db.scalar(select(PendingUpload).where(PendingUpload.storage_key == storage_key))
    if pending is None:
        raise HTTPException(status_code=404, detail="Upload not initialized")

    if pending.expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(status_code=401, detail="Upload token expired")

    if pending.byte_size > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    body = await request.body()
    if len(body) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    if pending.byte_size and len(body) != pending.byte_size:
        raise HTTPException(status_code=400, detail="Byte size mismatch")

    storage = get_upload_storage()
    sha = storage.write_bytes(storage_key, body)

    try:
        from io import BytesIO

        with Image.open(BytesIO(body)) as img:
            width, height = img.size
    except Exception:  # noqa: BLE001
        width, height = None, None

    pending.sha256 = sha
    pending.width_px = width
    pending.height_px = height
    db.commit()

    return {"status": "uploaded", "sha256": sha, "width_px": width or 0, "height_px": height or 0}


@router.post("/projects/{project_id}/uploads/complete", response_model=ProjectImageOut)
def upload_complete(
    project_id: int,
    body: UploadCompleteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectImage:
    settings = get_settings()
    _get_project(db, user.id, project_id)

    pending = db.scalar(
        select(PendingUpload).where(
            PendingUpload.project_id == project_id,
            PendingUpload.user_id == user.id,
            PendingUpload.storage_key == body.storage_key,
        )
    )
    if pending is None:
        raise HTTPException(status_code=404, detail="Pending upload not found")

    if pending.expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(status_code=400, detail="Upload expired")

    if pending.sha256 is None:
        raise HTTPException(status_code=400, detail="Upload not received")

    if body.sha256 and body.sha256 != pending.sha256:
        raise HTTPException(status_code=400, detail="SHA mismatch")

    existing_count = db.scalar(
        select(func.count(ProjectImage.id)).where(ProjectImage.project_id == project_id)
    )
    if existing_count is not None and existing_count >= settings.max_images_per_project:
        raise HTTPException(status_code=400, detail="Too many images in project")

    max_ordinal = db.scalar(select(func.max(ProjectImage.ordinal)).where(ProjectImage.project_id == project_id))
    next_ordinal = int(max_ordinal or 0) + 1

    image = ProjectImage(
        project_id=project_id,
        ordinal=next_ordinal,
        original_filename=pending.original_filename,
        content_type=pending.content_type,
        byte_size=pending.byte_size,
        sha256=pending.sha256,
        storage_key=pending.storage_key,
        width_px=body.width_px or pending.width_px,
        height_px=body.height_px or pending.height_px,
    )
    db.add(image)

    pending.completed_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(image)
    return image


@router.patch("/projects/{project_id}/images/reorder")
def reorder_images(
    project_id: int,
    body: ReorderImagesIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _get_project(db, user.id, project_id)

    images = db.scalars(select(ProjectImage).where(ProjectImage.project_id == project_id)).all()
    image_by_id = {img.id: img for img in images}

    if set(body.image_ids) != set(image_by_id.keys()):
        raise HTTPException(status_code=400, detail="image_ids must contain all project images")

    for idx, image_id in enumerate(body.image_ids, start=1):
        image_by_id[image_id].ordinal = idx

    db.commit()
    return {"status": "ok"}


@router.get("/projects/{project_id}/images/{image_id}/file")
def get_image_file(
    project_id: int,
    image_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse

    _get_project(db, user.id, project_id)

    image = db.scalar(
        select(ProjectImage).where(ProjectImage.id == image_id, ProjectImage.project_id == project_id)
    )
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    storage = get_upload_storage()
    path = storage.path_for_key(image.storage_key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing")

    return FileResponse(path, media_type=image.content_type)


@router.delete("/projects/{project_id}/images/{image_id}")
def delete_image(
    project_id: int,
    image_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _get_project(db, user.id, project_id)

    image = db.scalar(
        select(ProjectImage).where(ProjectImage.id == image_id, ProjectImage.project_id == project_id)
    )
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    db.delete(image)
    db.commit()
    return {"status": "deleted"}
