import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
from saas.api.models import Job, JobEvent, JobArtifact, Project, ProjectImage
from saas.worker.steps import (
    validate_inputs_step,
    extract_layouts_step,
    postprocess_layouts_step,
    upload_assets_step,
    create_presentation_step,
    build_slides_step,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConversionEngine:
    """Wrapper around images2slides library for SaaS integration"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def run(self, job: Job) -> Dict[str, Any]:
        """Run the complete conversion pipeline for a job"""
        logger.info(f"Starting conversion for job {job.id}")
        
        # Define pipeline steps
        steps = [
            ("validate_inputs", validate_inputs_step),
            ("extract_layouts", extract_layouts_step),
            ("postprocess_layouts", postprocess_layouts_step),
            ("upload_assets", upload_assets_step),
            ("create_presentation", create_presentation_step),
            ("build_slides", build_slides_step),
        ]
        
        result = {}
        
        for step_name, step_func in steps:
            logger.info(f"Running step: {step_name}")
            
            # Record step start
            event = JobEvent(
                job_id=job.id,
                step=step_name,
                status="started",
                started_at=datetime.utcnow()
            )
            self.db.add(event)
            self.db.commit()
            
            try:
                # Execute step
                step_result = step_func(job, self.db)
                result.update(step_result)
                
                # Record step completion
                event.status = "completed"
                event.finished_at = datetime.utcnow()
                event.duration_seconds = int((event.finished_at - event.started_at).total_seconds())
                self.db.commit()
                
                logger.info(f"Step {step_name} completed in {event.duration_seconds}s")
                
            except Exception as e:
                # Record step failure
                event.status = "failed"
                event.finished_at = datetime.utcnow()
                event.duration_seconds = int((event.finished_at - event.started_at).total_seconds())
                event.message = str(e)
                self.db.commit()
                
                logger.error(f"Step {step_name} failed: {e}")
                raise
        
        logger.info(f"Conversion completed for job {job.id}")
        return result
