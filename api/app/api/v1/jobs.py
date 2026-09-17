import contextlib
import json
import uuid
from typing import Annotated

from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from kombu.exceptions import KombuError
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from worker.outbox_dispatcher import dispatch_pending

from ...config import settings
from ...db.session import get_db
from ...models.job import Job, JobAttempt, JobStatus, JobType
from ...models.media import Mix
from ...models.outbox import OutboxMessage
from ...schemas.job import JobCreateRequest, JobOut
from ...services.job_commands import enqueue_job
from ...services.job_events import stream_job_events
from ..deps import require_api_key

router = APIRouter()
celery_client = Celery("mix_analyst_client", broker=settings.celery_broker_url)


@router.post(
    "/mixes/{mix_id}/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED
)
def create_mix_job(
    mix_id: str,
    req: JobCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    _auth: Annotated[None, Depends(require_api_key)],
):
    """Dispatch an asynchronous analysis/processing job for a mix.

    The job and its broker dispatch command commit atomically (outbox);
    a down broker leaves the job QUEUED and retryable instead of failing
    the request.
    """
    mix = db.query(Mix).filter(Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found"
        )

    try:
        job_type = (
            JobType[req.job_type.upper()]
            if req.job_type.upper() in JobType.__members__
            else JobType.ANALYSIS
        )
    except (AttributeError, KeyError):
        job_type = JobType.ANALYSIS

    def _send(task_name: str, args: list, task_id: str, queue: str) -> str:
        return celery_client.send_task(
            task_name, args=args, task_id=task_id, queue=queue
        ).id

    return enqueue_job(
        db,
        mix_id=mix.id,
        job_type=job_type,
        task_name="tasks.run_analysis_pipeline",
        task_args=lambda new_id: [new_id],
        queue="analysis",
        sender=_send,
    )


@router.get("/mixes/{mix_id}/jobs", response_model=list[JobOut])
def list_mix_jobs(mix_id: str, db: Annotated[Session, Depends(get_db)]):
    """List all jobs dispatched for a mix, newest first (powers the PWA panel)."""
    mix = db.query(Mix).filter(Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found"
        )
    jobs = (
        db.query(Job).filter(Job.mix_id == mix_id).order_by(Job.created_at.desc()).all()
    )
    return jobs


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Annotated[Session, Depends(get_db)]):
    """Get the current status and stage runs for a job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return job


@router.get("/jobs/{job_id}/events")
async def get_job_events(job_id: str):
    """Subscribe to real-time Server-Sent Events (SSE) for job progress."""
    return StreamingResponse(
        stream_job_events(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
    _auth: Annotated[None, Depends(require_api_key)],
):
    """Cancel an active or queued job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    if job.status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED]:
        return job

    if job.celery_task_id:
        # Best-effort revocation: the broker may already be gone.
        with contextlib.suppress(KombuError, RedisError, OSError):
            celery_client.control.revoke(
                job.celery_task_id, terminate=True, signal="SIGTERM"
            )

    job.status = JobStatus.CANCELLED
    job.error_message = "Cancelled by user request"
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
def retry_job(
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
    _auth: Annotated[None, Depends(require_api_key)],
):
    """Retry a failed or cancelled job as a new attempt."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    if job.status not in [JobStatus.FAILED, JobStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed or cancelled jobs can be retried",
        )

    # Record new attempt
    attempt_count = db.query(JobAttempt).filter(JobAttempt.job_id == job.id).count()
    new_attempt = JobAttempt(
        id=str(uuid.uuid4()),
        job_id=job.id,
        attempt_number=attempt_count + 1,
        status=JobStatus.QUEUED,
    )
    db.add(new_attempt)

    job.status = JobStatus.QUEUED
    job.progress_percent = 0.0
    job.current_stage = "Re-queued"
    job.error_message = None
    db.commit()

    # A retry is a fresh dispatch command: commit it to the outbox, then
    # attempt one inline delivery (a down broker keeps it retryable).
    db.add(
        OutboxMessage(
            id=str(uuid.uuid4()),
            aggregate_id=job.id,
            kind="job.dispatch",
            payload=json.dumps(
                {
                    "task_name": "tasks.run_analysis_pipeline",
                    "args": [job.id],
                    "task_id": f"job_{job.id}_att_{new_attempt.attempt_number}",
                    "queue": "analysis",
                }
            ),
        )
    )
    db.commit()

    def _send(task_name: str, args: list, task_id: str, queue: str) -> str:
        return celery_client.send_task(
            task_name, args=args, task_id=task_id, queue=queue
        ).id

    with contextlib.suppress(KombuError, RedisError, OSError):
        dispatch_pending(db, _send, job_ids=[job.id])

    db.refresh(job)
    return job
