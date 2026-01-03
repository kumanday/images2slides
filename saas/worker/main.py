import time
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from saas.api.database import SessionLocal, engine
from saas.api.models import Job, JobStatus, JobEvent
from saas.worker.conversion_engine import ConversionEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def claim_job(db: Session) -> Job | None:
    """Claim a queued job using row-level locking"""
    try:
        job = db.execute(
            select(Job)
            .where(Job.status == JobStatus.queued)
            .with_for_update(skip_locked=True)
            .order_by(Job.created_at)
            .limit(1)
        ).scalar_one_or_none()
        
        if job:
            job.status = JobStatus.running
            db.commit()
            db.refresh(job)
            logger.info(f"Claimed job {job.id}")
        
        return job
    except Exception as e:
        logger.error(f"Error claiming job: {e}")
        db.rollback()
        return None


def run_job(job: Job, db: Session):
    """Execute a job through the conversion pipeline"""
    engine = ConversionEngine(db)
    
    try:
        # Run the conversion pipeline
        result = engine.run(job)
        
        # Update job with result
        job.status = JobStatus.succeeded
        job.presentation_id = result.get("presentation_id")
        job.presentation_url = result.get("presentation_url")
        db.commit()
        
        logger.info(f"Job {job.id} completed successfully")
    except Exception as e:
        logger.error(f"Job {job.id} failed: {e}")
        job.status = JobStatus.failed
        job.error_message = str(e)
        db.commit()


def main():
    """Main worker loop"""
    logger.info("Starting worker...")
    
    while True:
        db = SessionLocal()
        try:
            job = claim_job(db)
            if job:
                run_job(job, db)
            else:
                time.sleep(1)  # No jobs, wait before polling again
        except Exception as e:
            logger.error(f"Worker error: {e}")
            time.sleep(5)  # Wait before retrying
        finally:
            db.close()


if __name__ == "__main__":
    main()
