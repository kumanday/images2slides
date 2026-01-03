"""Worker main entry point for processing jobs."""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path for imports
sys.path.insert(0, "/app")

from saas.backend.config import settings
from saas.backend.db.session import async_session_maker
from saas.backend.db.models import Job, JobEvent
from saas.worker.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_event = asyncio.Event()


def handle_shutdown(sig, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_event.set()


async def claim_job(db: AsyncSession) -> Job | None:
    """Claim a queued job using row locking.
    
    Uses FOR UPDATE SKIP LOCKED to safely claim a job
    without blocking other workers.
    
    Args:
        db: Database session.
        
    Returns:
        Claimed job or None if no jobs available.
    """
    # Find and lock a queued job
    result = await db.execute(
        select(Job)
        .where(Job.status == "queued")
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()

    if job is None:
        return None

    # Mark as running
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    await db.flush()

    # Log job start
    event = JobEvent(
        job_id=job.id,
        level="info",
        event_type="job_started",
        message=f"Job started (attempt {job.attempt})",
        data_json={"config": job.config_json},
    )
    db.add(event)
    await db.commit()

    logger.info(f"Claimed job {job.id} for project {job.project_id}")
    return job


async def complete_job(
    db: AsyncSession,
    job_id: int,
    success: bool,
    presentation_id: str | None = None,
    presentation_url: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Mark a job as completed.
    
    Args:
        db: Database session.
        job_id: Job ID.
        success: Whether job succeeded.
        presentation_id: Google Slides presentation ID.
        presentation_url: URL to the presentation.
        error_code: Error code if failed.
        error_message: Error message if failed.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        logger.error(f"Job {job_id} not found for completion")
        return

    job.status = "succeeded" if success else "failed"
    job.finished_at = datetime.now(timezone.utc)

    if presentation_id:
        job.presentation_id = presentation_id
    if presentation_url:
        job.presentation_url = presentation_url
    if error_code:
        job.error_code = error_code
    if error_message:
        job.error_message = error_message

    # Log completion
    event = JobEvent(
        job_id=job.id,
        level="info" if success else "error",
        event_type="job_completed" if success else "job_failed",
        message=f"Job {'succeeded' if success else 'failed'}",
        data_json={
            "presentation_id": presentation_id,
            "presentation_url": presentation_url,
            "error_code": error_code,
            "error_message": error_message,
        },
    )
    db.add(event)
    await db.commit()

    logger.info(
        f"Job {job_id} completed: {'success' if success else 'failed'}"
        + (f" - {error_message}" if error_message else "")
    )


async def update_job_step(
    db: AsyncSession,
    job_id: int,
    step: str,
    message: str | None = None,
) -> None:
    """Update job step and log event.
    
    Args:
        db: Database session.
        job_id: Job ID.
        step: New step name.
        message: Optional message.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        return

    job.step = step

    event = JobEvent(
        job_id=job.id,
        level="info",
        event_type="step_started",
        message=message or f"Starting step: {step}",
        data_json={"step": step},
    )
    db.add(event)
    await db.commit()


async def process_job(job: Job) -> None:
    """Process a single job.
    
    Args:
        job: Job to process.
    """
    async with async_session_maker() as db:
        try:
            # Run the pipeline
            result = await run_pipeline(db, job)

            # Complete the job
            await complete_job(
                db,
                job.id,
                success=result.success,
                presentation_id=result.presentation_id,
                presentation_url=result.presentation_url,
                error_code=result.error_code,
                error_message=result.error_message,
            )

        except Exception as e:
            logger.exception(f"Unhandled error processing job {job.id}")
            await complete_job(
                db,
                job.id,
                success=False,
                error_code="INTERNAL_ERROR",
                error_message=str(e),
            )


async def worker_loop() -> None:
    """Main worker loop that polls for and processes jobs."""
    logger.info("Worker started, polling for jobs...")

    while not shutdown_event.is_set():
        try:
            async with async_session_maker() as db:
                job = await claim_job(db)

            if job:
                await process_job(job)
            else:
                # No jobs available, wait before polling again
                try:
                    await asyncio.wait_for(
                        shutdown_event.wait(),
                        timeout=settings.job_poll_interval_seconds,
                    )
                except asyncio.TimeoutError:
                    pass

        except Exception as e:
            logger.exception("Error in worker loop")
            # Wait a bit before retrying to avoid tight error loops
            await asyncio.sleep(5)

    logger.info("Worker shutdown complete")


def main() -> None:
    """Entry point for the worker."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Run the worker loop
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()