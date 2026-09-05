"""Transactional storage and guarded terminal transitions for job events."""

from datetime import datetime, timezone

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from ..models.job import Job, JobAttempt, JobStatus
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
    attempt_number = db.scalar(
        select(JobAttempt.attempt_number)
        .where(JobAttempt.job_id == job.id)
        .order_by(JobAttempt.attempt_number.desc())
        .limit(1)
    )
    event = JobEvent(
        project_id=job.project_id,
        job_id=job.id,
        attempt_number=attempt_number or 1,
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
    finish_time = datetime.now(timezone.utc)
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
            finished_at=finish_time,
        )
    )
    if result.rowcount != 1:
        db.refresh(job)
        return job

    # Terminalize the active lease before a retry can create a newer attempt.
    db.execute(
        update(JobAttempt)
        .where(JobAttempt.job_id == job.id, JobAttempt.status == JobStatus.RUNNING)
        .values(
            status=JobStatus.CANCELLED,
            error_details="Cancelled by user request",
            finished_at=finish_time,
            lease_expires_at=finish_time,
        )
    )
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


def complete_job_attempt(
    db: Session,
    job_id: str,
    project_id: str,
    worker_name: str,
    attempt_number: int | None = None,
    claim_token: str | None = None,
    *,
    now: datetime | None = None,
) -> bool:
    """Finalize only the running attempt claimed by this trusted worker.

    The owning project and claim identity are part of the terminal transition
    predicate, not merely routing metadata. The success event is inserted in
    this transaction so a worker cannot commit a terminal state without a
    replayable terminal event.
    """
    finish_time = now or datetime.now(timezone.utc)
    claimed_attempt_conditions = [
        JobAttempt.job_id == job_id,
        JobAttempt.status == JobStatus.RUNNING,
        JobAttempt.worker_hostname == worker_name,
        # Matching a token is necessary but not sufficient: after this instant
        # a redelivery may lawfully reclaim the attempt.  Do not let a paused
        # worker publish a terminal state during that ownership gap.
        JobAttempt.lease_expires_at > finish_time,
    ]
    if attempt_number is not None:
        claimed_attempt_conditions.append(JobAttempt.attempt_number == attempt_number)
    if claim_token is not None:
        claimed_attempt_conditions.append(JobAttempt.claim_token == claim_token)
    claimed_attempt = exists(select(JobAttempt.id).where(*claimed_attempt_conditions))
    completed_job_id = db.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.project_id == project_id,
            Job.status == JobStatus.RUNNING,
            claimed_attempt,
        )
        .values(
            status=JobStatus.SUCCEEDED,
            progress_percent=100.0,
            current_stage="Complete",
            finished_at=finish_time,
        )
        .returning(Job.id)
    ).scalar_one_or_none()
    if completed_job_id is None:
        return False

    completed_attempt_conditions = [
        JobAttempt.job_id == completed_job_id,
        JobAttempt.status == JobStatus.RUNNING,
        JobAttempt.worker_hostname == worker_name,
        JobAttempt.lease_expires_at > finish_time,
    ]
    if attempt_number is not None:
        completed_attempt_conditions.append(JobAttempt.attempt_number == attempt_number)
    if claim_token is not None:
        completed_attempt_conditions.append(JobAttempt.claim_token == claim_token)
    completed_attempt_id = db.execute(
        update(JobAttempt)
        .where(*completed_attempt_conditions)
        .values(status=JobStatus.SUCCEEDED, finished_at=finish_time)
        .returning(JobAttempt.id)
    ).scalar_one_or_none()
    if completed_attempt_id is None:
        raise RuntimeError(f"Running job {job_id} has no attempt claimed by {worker_name}")

    job = db.scalar(select(Job).where(Job.id == completed_job_id, Job.project_id == project_id))
    if job is None:
        raise RuntimeError(f"Completed job {job_id} is outside project {project_id}")
    record_job_event(
        db,
        job,
        "update",
        {
            "job_id": job_id,
            "status": JobStatus.SUCCEEDED.value,
            "progress_percent": 100.0,
            "current_stage": "Complete",
        },
    )
    return True
