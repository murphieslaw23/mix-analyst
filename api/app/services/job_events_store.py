"""Transactional storage and guarded terminal transitions for job events."""

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..models.job import Job, JobStatus
from ..models.job_event import JobEvent


def record_job_event(db: Session, job: Job, event_type: str, payload: dict) -> JobEvent:
    """Append an event using the job row as an atomic per-job sequence counter.

    The increment and inserted event share the caller's transaction.  Database
    row locking on the ``jobs`` update serializes competing writers for one job
    while allowing unrelated jobs to progress independently.
    """
    sequence = db.execute(
        update(Job)
        .where(Job.id == job.id, Job.project_id == job.project_id)
        .values(event_sequence=Job.event_sequence + 1)
        .returning(Job.event_sequence)
    ).scalar_one()
    event = JobEvent(
        project_id=job.project_id,
        job_id=job.id,
        sequence=sequence,
        event_type=event_type,
        payload=payload,
    )
    db.add(event)
    db.flush()
    return event


def request_cancellation(db: Session, job: Job) -> Job:
    """Atomically let cancellation win a queued/running job without killing work.

    A worker that reaches a later checkpoint sees the authoritative CANCELLED
    status.  The cancellation event is committed in the same transaction as
    that state change, so replay always represents the winning terminal state.
    """
    result = db.execute(
        update(Job)
        .where(
            Job.id == job.id,
            Job.project_id == job.project_id,
            Job.status.in_((JobStatus.QUEUED, JobStatus.RUNNING)),
        )
        .values(
            status=JobStatus.CANCELLED,
            error_message="Cancelled by user request",
            finished_at=datetime.now(timezone.utc),
        )
    )
    if result.rowcount != 1:
        db.refresh(job)
        return job

    db.refresh(job)
    record_job_event(
        db,
        job,
        "update",
        {
            "job_id": job.id,
            "status": JobStatus.CANCELLED.value,
            "progress_percent": job.progress_percent,
            "current_stage": job.current_stage,
            "error_message": job.error_message,
        },
    )
    return job


def complete_job_attempt(db: Session, job_id: str, worker_name: str) -> bool:
    """Mark a running job successful only while its authoritative state permits it.

    ``worker_name`` is part of the worker-facing contract; ownership of the
    running attempt is finalized by the scoped worker transition that calls
    this guard.  The conditional job update is the cancellation race gate.
    """
    del worker_name
    result = db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.RUNNING)
        .values(
            status=JobStatus.SUCCEEDED,
            progress_percent=100.0,
            current_stage="Complete",
            finished_at=datetime.now(timezone.utc),
        )
    )
    return result.rowcount == 1
