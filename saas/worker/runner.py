from __future__ import annotations


import os

import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from sqlalchemy import select
from sqlalchemy.orm import Session

from images2slides.build_slide import (
    SlidesAPIError,
    apply_requests,
    build_requests_for_infographic,
    create_presentation,
    delete_initial_slide,
    get_page_size_pt,
)
from images2slides.geometry import compute_fit
from images2slides.slides_api import req_delete_slide


from images2slides.models import Layout
from images2slides.vlm import VLMConfig

from saas.backend.config import get_settings
from saas.backend.db.models import (
    Artifact,
    ArtifactKind,
    EventLevel,
    Job,
    JobStatus,
    JobStep,
    JobEvent,
    OAuthToken,
    Project,
    ProjectImage,
)
from saas.backend.db.session import SessionLocal
from saas.backend.services.conversion_engine import PAGE_SIZE_MAP, extract_layouts, postprocess, upload_assets
from saas.backend.services.crypto import Crypto
from saas.backend.services.google_oauth import build_slides_service, get_google_credentials_for_user
from saas.backend.storage import get_artifact_storage, get_upload_storage


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@contextmanager
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def log_event(
    db: Session,
    job_id: int,
    level: EventLevel,
    event_type: str,
    message: str,
    data_json: dict[str, Any] | None = None,
) -> None:
    db.add(
        JobEvent(
            job_id=job_id,
            level=level,
            event_type=event_type,
            message=message,
            data_json=data_json,
        )
    )


def store_artifact_json(
    db: Session,
    job_id: int,
    kind: ArtifactKind,
    storage_key: str,
    payload: Any,
    metadata: dict[str, Any] | None = None,
) -> Artifact:
    storage = get_artifact_storage()
    sha = storage.write_json(storage_key, payload)

    art = Artifact(job_id=job_id, kind=kind, storage_key=storage_key, sha256=sha, metadata=metadata)
    db.add(art)
    return art


def _job_artifact_exists(db: Session, job_id: int, kind: ArtifactKind, storage_key: str) -> bool:
    return (
        db.scalar(
            select(Artifact.id).where(
                Artifact.job_id == job_id,
                Artifact.kind == kind,
                Artifact.storage_key == storage_key,
            )
        )
        is not None
    )


def claim_next_job() -> int | None:
    with db_session() as db:
        with db.begin():
            job = (
                db.execute(
                    select(Job)
                    .where(Job.status == JobStatus.queued)
                    .order_by(Job.created_at.asc())
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if job is None:
                return None

            job.status = JobStatus.running
            job.step = JobStep.validate_inputs
            job.started_at = utcnow()
            log_event(db, job.id, EventLevel.info, "job.claimed", "Job claimed")

        return int(job.id)


def run_job(job_id: int) -> None:
    settings = get_settings()
    crypto = Crypto(settings)

    with db_session() as db:
        job = db.scalar(select(Job).where(Job.id == job_id))
        if job is None:
            return

        project = db.scalar(select(Project).where(Project.id == job.project_id))
        if project is None:
            _fail_job(db, job, "project_missing", "Project not found")
            return

        images = db.scalars(
            select(ProjectImage).where(ProjectImage.project_id == project.id).order_by(ProjectImage.ordinal.asc())
        ).all()

        try:
            _step_validate_inputs(db, job, project, images)
            _step_extract_layouts(db, job, images)
            _step_postprocess_layouts(db, job, images)
            _step_upload_assets(db, job, images)
            _step_create_presentation(db, job, project, crypto, settings)
            _step_build_slides(db, job, project, images, crypto, settings)

            job.status = JobStatus.succeeded
            job.step = JobStep.finalize
            job.finished_at = utcnow()
            log_event(db, job.id, EventLevel.info, "job.succeeded", "Job succeeded")
            db.commit()

        except Exception as e:  # noqa: BLE001
            _fail_job(db, job, "exception", str(e), exc=e)


def _fail_job(db: Session, job: Job, code: str, message: str, exc: Exception | None = None) -> None:
    job.status = JobStatus.failed
    job.error_code = code
    job.error_message = (message or "").strip()[:500]
    job.finished_at = utcnow()

    log_event(db, job.id, EventLevel.error, "job.failed", job.error_message, {"error_code": code})

    if exc is not None:
        trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        storage_key = f"jobs/{job.id}/trace.txt"
        storage = get_artifact_storage()
        sha = storage.write_bytes(storage_key, trace.encode("utf-8"))
        db.add(
            Artifact(
                job_id=job.id,
                kind=ArtifactKind.trace,
                storage_key=storage_key,
                sha256=sha,
                metadata=None,
            )
        )

    db.commit()


def _step_validate_inputs(db: Session, job: Job, project: Project, images: list[ProjectImage]) -> None:
    job.step = JobStep.validate_inputs
    db.commit()

    if not images:
        raise ValueError("Project has no images")

    oauth = db.scalar(select(OAuthToken).where(OAuthToken.user_id == job.user_id, OAuthToken.provider == "google"))
    if oauth is None:
        raise ValueError("User has not granted Google permissions yet")

    manifest = {
        "project_id": project.id,
        "job_id": job.id,
        "images": [
            {
                "project_image_id": img.id,
                "ordinal": img.ordinal,
                "sha256": img.sha256,
                "storage_key": img.storage_key,
                "content_type": img.content_type,
                "byte_size": img.byte_size,
            }
            for img in images
        ],
    }
    storage_key = f"jobs/{job.id}/input_manifest.json"
    if not _job_artifact_exists(db, job.id, ArtifactKind.input_manifest, storage_key):
        store_artifact_json(db, job.id, ArtifactKind.input_manifest, storage_key, manifest)

    log_event(db, job.id, EventLevel.info, "step.validate_inputs", "Inputs validated")
    db.commit()


def _step_extract_layouts(db: Session, job: Job, images: list[ProjectImage]) -> None:
    job.step = JobStep.extract_layouts
    db.commit()

    upload_storage = get_upload_storage()

    vlm_config = VLMConfig(
        provider=os.environ.get("VLM_PROVIDER", "google"),
        model=os.environ.get("VLM_MODEL"),
    )

    image_paths: list[Path] = [upload_storage.path_for_key(img.storage_key) for img in images]

    layouts: list[Layout] = []
    for idx, (img, path) in enumerate(zip(images, image_paths, strict=False), start=1):
        storage_key = f"jobs/{job.id}/layouts/raw_{idx:03d}_{img.sha256}.json"
        existing = db.scalar(
            select(Artifact).where(
                Artifact.job_id == job.id,
                Artifact.kind == ArtifactKind.layout_raw,
                Artifact.storage_key == storage_key,
            )
        )
        if existing is not None and get_artifact_storage().exists(storage_key):
            data = get_artifact_storage().read_bytes(storage_key).decode("utf-8")
            layouts.append(Layout.from_json(data))
            continue

        extracted = extract_layouts([path], vlm_config=vlm_config)[0]
        layouts.append(extracted)
        store_artifact_json(
            db,
            job.id,
            ArtifactKind.layout_raw,
            storage_key,
            extracted.to_dict(),
            metadata={"project_image_id": img.id, "sha256": img.sha256},
        )
        db.commit()

    log_event(db, job.id, EventLevel.info, "step.extract_layouts", "Layouts extracted", {"count": len(layouts)})
    db.commit()


def _step_postprocess_layouts(db: Session, job: Job, images: list[ProjectImage]) -> None:
    job.step = JobStep.postprocess_layouts
    db.commit()

    raw_layouts: list[Layout] = []
    for idx, img in enumerate(images, start=1):
        raw_key = f"jobs/{job.id}/layouts/raw_{idx:03d}_{img.sha256}.json"
        raw_json = get_artifact_storage().read_bytes(raw_key).decode("utf-8")
        raw_layouts.append(Layout.from_json(raw_json))

    clean_layouts = postprocess(raw_layouts)

    for idx, (img, layout) in enumerate(zip(images, clean_layouts, strict=False), start=1):
        clean_key = f"jobs/{job.id}/layouts/clean_{idx:03d}_{img.sha256}.json"
        if _job_artifact_exists(db, job.id, ArtifactKind.layout_clean, clean_key) and get_artifact_storage().exists(clean_key):
            continue
        store_artifact_json(
            db,
            job.id,
            ArtifactKind.layout_clean,
            clean_key,
            layout.to_dict(),
            metadata={"project_image_id": img.id, "sha256": img.sha256},
        )
        db.commit()

    run_cfg_key = f"jobs/{job.id}/run_config.json"
    if not _job_artifact_exists(db, job.id, ArtifactKind.run_config, run_cfg_key):
        cfg = {
            "vlm_provider": os.environ.get("VLM_PROVIDER", "google"),
            "vlm_model": os.environ.get("VLM_MODEL"),
        }
        store_artifact_json(db, job.id, ArtifactKind.run_config, run_cfg_key, cfg)
        db.commit()

    log_event(db, job.id, EventLevel.info, "step.postprocess_layouts", "Layouts postprocessed")
    db.commit()


def _step_upload_assets(db: Session, job: Job, images: list[ProjectImage]) -> None:
    job.step = JobStep.upload_assets
    db.commit()

    # v0.1: optional/disabled.
    log_event(db, job.id, EventLevel.info, "step.upload_assets", "Asset upload skipped")
    db.commit()


def _get_slides_service(db: Session, user_id: int, crypto: Crypto, settings: Any):
    scopes = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/presentations",
        "https://www.googleapis.com/auth/drive.file",
    ]
    creds = get_google_credentials_for_user(db, settings, crypto, user_id, scopes=scopes)
    return build_slides_service(creds)


def _step_create_presentation(
    db: Session,
    job: Job,
    project: Project,
    crypto: Crypto,
    settings: Any,
) -> None:
    job.step = JobStep.create_presentation
    db.commit()

    if job.presentation_id:
        log_event(db, job.id, EventLevel.info, "step.create_presentation", "Presentation already exists")
        db.commit()
        return

    preset = PAGE_SIZE_MAP.get(project.page_size)
    if preset is None:
        raise ValueError(f"Unsupported page_size: {project.page_size}")

    service = _get_slides_service(db, job.user_id, crypto, settings)

    presentation_id, _w_pt, _h_pt = create_presentation(service=service, title=project.title, page_size=preset)

    job.presentation_id = presentation_id
    job.presentation_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    db.commit()

    log_event(
        db,
        job.id,
        EventLevel.info,
        "step.create_presentation",
        "Presentation created",
        {"presentation_id": presentation_id},
    )
    db.commit()


def _step_build_slides(
    db: Session,
    job: Job,
    project: Project,
    images: list[ProjectImage],
    crypto: Crypto,
    settings: Any,
) -> None:
    job.step = JobStep.build_slides
    db.commit()

    if not job.presentation_id:
        raise ValueError("Missing presentation_id")

    service = _get_slides_service(db, job.user_id, crypto, settings)

    clean_layouts: list[Layout] = []
    for idx, img in enumerate(images, start=1):
        clean_key = f"jobs/{job.id}/layouts/clean_{idx:03d}_{img.sha256}.json"
        clean_json = get_artifact_storage().read_bytes(clean_key).decode("utf-8")
        clean_layouts.append(Layout.from_json(clean_json))

    upload_storage = get_upload_storage()
    image_paths = [upload_storage.path_for_key(img.storage_key) for img in images]
    layouts_with_urls = upload_assets(clean_layouts, image_paths)

    # Ensure idempotency by clearing any existing slides.
    try:
        pres = service.presentations().get(presentationId=job.presentation_id).execute()
        slide_ids = [s["objectId"] for s in pres.get("slides", [])]
        if slide_ids:
            apply_requests(service, job.presentation_id, [req_delete_slide(sid) for sid in slide_ids])
    except Exception:
        # If clearing fails, proceed; build may still succeed.
        pass

    # Delete initial slide if present (safe to ignore failures).
    try:
        delete_initial_slide(service, job.presentation_id)
    except Exception:
        pass

    slide_w_pt, slide_h_pt = get_page_size_pt(service, job.presentation_id)

    all_requests: list[dict] = []
    for i, item in enumerate(layouts_with_urls):
        slide_id = f"SLIDE_{i:03d}"
        layout: Layout = item["layout"]
        fit = compute_fit(layout.image_px.width, layout.image_px.height, slide_w_pt, slide_h_pt)
        reqs = build_requests_for_infographic(
            slide_id=slide_id,
            layout=layout,
            fit=fit,
            cropped_url_by_region_id=item.get("cropped_url_by_region_id"),
            place_background=False,
        )
        for req in reqs:
            if "createSlide" in req:
                req["createSlide"]["insertionIndex"] = i
        all_requests.extend(reqs)

    try:
        apply_requests(service, job.presentation_id, all_requests)
    except SlidesAPIError as e:
        raise RuntimeError(str(e)) from e

    log_event(
        db,
        job.id,
        EventLevel.info,
        "step.build_slides",
        "Slides built",
        {"presentation_id": job.presentation_id, "num_slides": len(layouts_with_urls)},
    )
    db.commit()
