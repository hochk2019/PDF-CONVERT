"""Celery tasks for running OCR jobs."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from .audit import append_job_log
from .celery_app import celery_app
from .database import session_scope
from .models import Job, JobStatus, LogLevel
from .pipeline import OCRPipeline, PipelineDependencyError

LOGGER = logging.getLogger(__name__)


@celery_app.task(name="backend.tasks.process_pdf")
def process_pdf(job_id: str) -> None:
    """Background task that performs OCR for a job."""

    with session_scope() as session:
        job = _get_job(session, job_id)
        if not job:
            LOGGER.error("job not found", extra={"job_id": job_id})
            return

        job.status = JobStatus.PROCESSING
        append_job_log(session, job, "Job picked up by worker.")
        session.flush()

        try:
            pipeline = OCRPipeline()
            result = pipeline.run(job_id, Path(job.input_path))
            job.status = JobStatus.COMPLETED
            job.result_path = str(result.output_path)
            job.result_payload = result.metadata
            append_job_log(session, job, "OCR pipeline completed successfully.")
        except PipelineDependencyError as exc:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            append_job_log(session, job, "Missing OCR dependency", level=LogLevel.ERROR)
            LOGGER.exception("Pipeline dependency missing for job %s", job_id)
        except Exception as exc:  # pragma: no cover - defensive catch-all
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            append_job_log(session, job, "Job failed", level=LogLevel.ERROR)
            LOGGER.exception("Unhandled exception while processing job %s", job_id)


def _get_job(session: Session, job_id: str) -> Job | None:
    try:
        identifier = uuid.UUID(job_id)
    except ValueError:
        LOGGER.error("invalid job id", extra={"job_id": job_id})
        return None
    return session.get(Job, identifier)
