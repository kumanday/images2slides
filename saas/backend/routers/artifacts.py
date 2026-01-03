from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Artifact, Job, User
from ..db.session import get_db
from ..services.auth import get_current_user
from ..storage import get_artifact_storage

router = APIRouter()


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(
    artifact_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    artifact = db.scalar(select(Artifact).where(Artifact.id == artifact_id))
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    job = db.scalar(select(Job).where(Job.id == artifact.job_id))
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Artifact not found")

    storage = get_artifact_storage()
    path = storage.path_for_key(artifact.storage_key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact file missing")

    filename = path.name
    return FileResponse(path, filename=filename)
