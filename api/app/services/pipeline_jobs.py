"""Shared helper for dispatching pipeline jobs (mastering, stems, sidechain, render).

Every pipeline trigger creates a generic Job row (visible via GET /jobs/{id}
and the SSE event stream) plus its domain row, then dispatches the Celery
task to the queue the worker actually consumes.
"""

from collections.abc import Callable

from celery import Celery
from fastapi import HTTPException, status
from kombu.exceptions import KombuError
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from ..config import settings
from ..models.job import Job, JobType

celery_client = Celery("mix_analyst_client", broker=settings.celery_broker_url)


def enqueue_pipeline_job(
    db: Session,
    *,
    mix_id: str,
    project_id: str,
    job_type: JobType,
    task_name: str,
    task_args: list | Callable[[str], list],
    queue: str,
) -> Job:
    """Create Job + attempt + outbox dispatch in one transaction.

    task_args may be a static list or a factory receiving the new Job id
    (pipeline tasks need both the generic job id and their domain row id).
    One inline broker delivery is attempted; a down broker leaves the job
    QUEUED with a retryable outbox row instead of failing the request.
    """
    from .job_commands import enqueue_job

    def _send(task_name: str, args: list, task_id: str, queue: str) -> str:
        return celery_client.send_task(
            task_name, args=args, task_id=task_id, queue=queue
        ).id

    try:
        return enqueue_job(
            db,
            mix_id=mix_id,
            project_id=project_id,
            job_type=job_type,
            task_name=task_name,
            task_args=task_args,
            queue=queue,
            sender=_send,
        )
    except (KombuError, RedisError, OSError) as e:
        # Only errors raised outside the outbox-guarded sender reach here.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Worker queue unavailable: {e}",
        )
