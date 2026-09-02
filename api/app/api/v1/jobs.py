from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from celery import Celery
import uuid

from ...db.session import get_db
from ..deps import get_current_principal, require_owned_job, require_owned_mix
from ...config import settings
from ...models.media import Mix
from ...models.job import Job, JobType, JobStatus, JobAttempt
from ...schemas.job import JobOut, JobCreateRequest
from ...schemas.auth import CurrentPrincipal
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

    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        mix_id=mix.id,
        project_id=principal.project_id,
        job_type=JobType[req.job_type.upper()] if req.job_type.upper() in JobType.__members__ else JobType.ANALYSIS,
        status=JobStatus.QUEUED,
        progress_percent=0.0,
        current_stage="Queued",
    )
    db.add(job)

    attempt = JobAttempt(
        id=str(uuid.uuid4()),
        job_id=job.id,
        attempt_number=1,
        status=JobStatus.QUEUED,
    )
    db.add(attempt)
    db.commit()
    db.refresh(job)

    # Dispatch to Celery worker queue
    try:
        async_result = celery_client.send_task(
            "tasks.run_analysis_pipeline",
            args=[job.id],
            task_id=f"job_{job.id}",
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
    require_owned_job(db, principal, job_id)
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

    try:
        async_result = celery_client.send_task(
            "tasks.run_analysis_pipeline",
            args=[job.id],
            task_id=f"job_{job.id}_att_{new_attempt.attempt_number}",
        )
        job.celery_task_id = async_result.id
        db.commit()
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error_message = f"Failed to re-dispatch to Celery: {e}"
        db.commit()

    db.refresh(job)
    return job
