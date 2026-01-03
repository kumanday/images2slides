from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..db.models import Job, JobStatus, JobStep, Project, ProjectStatus, User
from ..db.session import get_db
from ..schemas import ArtifactOut, GenerateIn, GenerateOut, JobEventOut, JobOut
from ..services.auth import get_current_user

router = APIRouter()


def _get_project(db: Session, user_id: int, project_id: int) -> Project:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.user_id == user_id, Project.status != ProjectStatus.archived)
        .options(selectinload(Project.images))
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_job(db: Session, user_id: int, job_id: int) -> Job:
    job = db.scalar(
        select(Job)
        .where(Job.id == job_id, Job.user_id == user_id)
        .options(selectinload(Job.events), selectinload(Job.artifacts))
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _idempotency_key(project: Project, title: str, page_size: str) -> str:
    payload = {
        "project_id": project.id,
        "title": title,
        "page_size": page_size,
        "images": [img.sha256 for img in project.images],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:40]


@router.post("/projects/{project_id}/generate", response_model=GenerateOut)
def generate(
    project_id: int,
    body: GenerateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerateOut:
    settings = get_settings()
    project = _get_project(db, user.id, project_id)

    if not project.images:
        raise HTTPException(status_code=400, detail="Project has no images")

    # Basic rate limit
    since = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    recent = db.scalar(select(func.count(Job.id)).where(Job.user_id == user.id, Job.created_at >= since))
    if recent is not None and recent >= settings.jobs_per_hour:
        raise HTTPException(status_code=429, detail="Too many jobs created recently")

    title = body.title or project.title
    page_size = body.page_size or project.page_size

    idem = _idempotency_key(project, title, page_size)

    existing = db.scalar(
        select(Job).where(
            Job.project_id == project.id,
            Job.idempotency_key == idem,
            Job.status.in_([JobStatus.queued, JobStatus.running]),
        )
    )
    if existing is not None:
        return GenerateOut(job_id=existing.id)

    attempt = (db.scalar(select(func.max(Job.attempt)).where(Job.project_id == project.id)) or 0) + 1

    job = Job(
        project_id=project.id,
        user_id=user.id,
        status=JobStatus.queued,
        step=JobStep.queued,
        attempt=int(attempt),
        idempotency_key=idem,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    project.latest_job_id = job.id
    db.commit()

    return GenerateOut(job_id=job.id)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    return _get_job(db, user.id, job_id)


@router.get("/jobs/{job_id}/events", response_model=list[JobEventOut])
def get_job_events(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Any]:
    job = _get_job(db, user.id, job_id)
    return list(job.events)


@router.get("/jobs/{job_id}/artifacts", response_model=list[ArtifactOut])
def get_job_artifacts(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ArtifactOut]:
    settings = get_settings()
    job = _get_job(db, user.id, job_id)

    out: list[ArtifactOut] = []
    for art in job.artifacts:
        dto = ArtifactOut.model_validate(art)
        dto.download_url = f"{settings.api_base_url}/api/v1/artifacts/{art.id}/download"
        out.append(dto)
    return out


@router.post("/jobs/{job_id}/retry", response_model=GenerateOut)
def retry_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerateOut:
    old = _get_job(db, user.id, job_id)
    project = _get_project(db, user.id, old.project_id)

    # Force a new idempotency key by salting with timestamp.
    salt = datetime.now(tz=timezone.utc).isoformat()
    payload = {"project_id": project.id, "salt": salt, "images": [img.sha256 for img in project.images]}
    idem = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:40]

    attempt = (db.scalar(select(func.max(Job.attempt)).where(Job.project_id == project.id)) or 0) + 1

    job = Job(
        project_id=project.id,
        user_id=user.id,
        status=JobStatus.queued,
        step=JobStep.queued,
        attempt=int(attempt),
        idempotency_key=idem,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    project.latest_job_id = job.id
    db.commit()

    return GenerateOut(job_id=job.id)
