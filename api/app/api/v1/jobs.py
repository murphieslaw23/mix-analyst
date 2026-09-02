from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from celery import Celery

from ...db.session import get_db
from ..deps import get_current_principal, require_owned_job, require_owned_mix
from ...config import settings
from ...models.job import JobStatus
from ...schemas.job import JobOut, JobCreateRequest
from ...schemas.auth import CurrentPrincipal
from ...services.job_commands import enqueue_job, enqueue_retry
from ...services.job_events import stream_job_events

router = APIRouter()
celery_client = Celery("mix_analyst_client", broker=settings.celery_broker_url)


@router.post("/mixes/{mix_id}/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_mix_job(
    mix_id: str,
    req: JobCreateRequest,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Dispatch an asynchronous analysis/processing job for a mix."""
    mix = require_owned_mix(db, principal, mix_id)

    job = enqueue_job(db, principal, mix, req)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Get the current status and stage runs for a job."""
    return require_owned_job(db, principal, job_id)


@router.get("/jobs/{job_id}/events")
async def get_job_events(
    job_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Subscribe to real-time Server-Sent Events (SSE) for job progress."""
    job = require_owned_job(db, principal, job_id)
    return StreamingResponse(
        stream_job_events(job.project_id, job.id),
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
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Cancel an active or queued job."""
    job = require_owned_job(db, principal, job_id)

    if job.status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED]:
        return job

    if job.celery_task_id:
        try:
            celery_client.control.revoke(job.celery_task_id, terminate=True, signal="SIGTERM")
        except Exception:
            pass

    job.status = JobStatus.CANCELLED
    job.error_message = "Cancelled by user request"
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
def retry_job(
    job_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Retry a failed or cancelled job as a new attempt."""
    job = require_owned_job(db, principal, job_id)

    if job.status not in [JobStatus.FAILED, JobStatus.CANCELLED]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed or cancelled jobs can be retried")

    enqueue_retry(db, job)
    db.commit()
    db.refresh(job)
    return job
