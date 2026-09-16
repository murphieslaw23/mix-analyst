"""Shared helper for dispatching pipeline jobs (mastering, stems, sidechain, render).

Every pipeline trigger creates a generic Job row (visible via GET /jobs/{id}
and the SSE event stream) plus its domain row, then dispatches the Celery
task to the queue the worker actually consumes.
"""
import uuid
from typing import Callable

from celery import Celery
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..models.job import Job, JobAttempt, JobStatus, JobType

celery_client = Celery("mix_analyst_client", broker=settings.celery_broker_url)


def enqueue_pipeline_job(
    db: Session,
    *,
    mix_id: str,
    job_type: JobType,
    task_name: str,
    task_args: list | Callable[[str], list],
    queue: str,
) -> Job:
    """Create Job + attempt rows and dispatch the Celery task. 503 if down.

    task_args may be a static list or a factory receiving the new Job id
    (pipeline tasks need both the generic job id and their domain row id).
    """
    job = Job(
        id=str(uuid.uuid4()),
        mix_id=mix_id,
        job_type=job_type,
        status=JobStatus.QUEUED,
        progress_percent=0.0,
        current_stage="Queued",
    )
    db.add(job)
    db.add(
        JobAttempt(
            id=str(uuid.uuid4()),
            job_id=job.id,
            attempt_number=1,
            status=JobStatus.QUEUED,
        )
    )
    db.commit()
    db.refresh(job)

    try:
        args = task_args(job.id) if callable(task_args) else task_args
        async_result = celery_client.send_task(
            task_name,
            args=args,
            task_id=f"job_{job.id}",
            queue=queue,
        )
        job.celery_task_id = async_result.id
        db.commit()
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error_message = f"Failed to dispatch to Celery: {e}"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Worker queue unavailable: {e}",
        )

    db.refresh(job)
    return job
