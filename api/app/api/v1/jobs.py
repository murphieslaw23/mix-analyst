from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...db.session import get_db
from ..deps import get_current_principal, require_owned_job, require_owned_mix
from ...models.job import JobStatus
from ...schemas.job import JobOut, JobCreateRequest
from ...schemas.auth import CurrentPrincipal
from ...services.job_commands import enqueue_job, enqueue_retry
from ...services.job_events import event_notification, publish_event, stream_job_events
from ...services.job_events_store import request_cancellation
from ...services.batches import recompute_batch_status

router = APIRouter()


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
    request: Request,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Subscribe to real-time Server-Sent Events (SSE) for job progress."""
    job = require_owned_job(db, principal, job_id)
    raw_last_event_id = request.headers.get("Last-Event-ID", "0")
    try:
        last_event_id = int(raw_last_event_id)
        if last_event_id < 0:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Last-Event-ID must be a non-negative integer") from None
    return StreamingResponse(
        stream_job_events(db, job.project_id, job.id, last_event_id),
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
    was_cancellable = job.status in (JobStatus.QUEUED, JobStatus.RUNNING)

    job = request_cancellation(db, job)
    if job.batch_id is not None:
        recompute_batch_status(db, job.batch_id)
    db.commit()
    db.refresh(job)
    cancellation_event = job.events[-1] if was_cancellable and job.events else None
    if cancellation_event is not None:
        publish_event(job.project_id, job.id, event_notification(cancellation_event))
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

    if enqueue_retry(db, job) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed or cancelled jobs can be retried")
    if job.batch_id is not None:
        recompute_batch_status(db, job.batch_id)
    db.commit()
    db.refresh(job)
    return job
