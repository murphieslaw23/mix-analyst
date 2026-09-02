"""Durable command creation and idempotent worker job claims."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models.job import Job, JobAttempt, JobStatus, JobType
from ..models.media import Mix
from ..models.outbox import OutboxMessage
from ..schemas.auth import CurrentPrincipal
from ..schemas.job import JobCreateRequest


TASK_NAME = "tasks.run_analysis_pipeline"

JOB_QUEUES = {
    JobType.ANALYSIS: "analysis-cpu",
    JobType.FINGERPRINT: "analysis-cpu",
    JobType.RESTORATION: "dsp-heavy",
    JobType.MASTERING: "dsp-heavy",
    JobType.EXPORT: "exports",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_job(db: Session, principal: CurrentPrincipal, mix: Mix, request: JobCreateRequest) -> Job:
    """Create a queued job, initial attempt, and broker command in one DB transaction.

    The caller owns the transaction boundary.  In particular, no broker call is
    made here: the outbox row cannot become visible without the matching job.
    """
    if mix.project_id != principal.project_id:
        raise PermissionError("Mix does not belong to the current project")

    job_type = JobType(request.job_type)
    job = Job(
        id=str(uuid.uuid4()),
        mix_id=mix.id,
        project_id=principal.project_id,
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
    db.add(
        OutboxMessage(
            project_id=principal.project_id,
            aggregate_id=job.id,
            kind="job.dispatch",
            payload={
                "job_id": job.id,
                "project_id": principal.project_id,
                "task_name": TASK_NAME,
                "task_id": f"job_{job.id}",
                "queue": JOB_QUEUES[job_type],
            },
        )
    )
    db.flush()
    return job


def enqueue_retry(db: Session, job: Job) -> JobAttempt:
    """Durably requeue a terminal job and create its next dispatch command."""
    attempt_number = (db.scalar(select(func.max(JobAttempt.attempt_number)).where(JobAttempt.job_id == job.id)) or 0) + 1
    attempt = JobAttempt(
        id=str(uuid.uuid4()),
        job_id=job.id,
        attempt_number=attempt_number,
        status=JobStatus.QUEUED,
    )
    db.add(attempt)
    job.status = JobStatus.QUEUED
    job.progress_percent = 0.0
    job.current_stage = "Re-queued"
    job.error_message = None
    job.started_at = None
    job.finished_at = None
    task_id = f"job_{job.id}_att_{attempt_number}"
    db.add(
        OutboxMessage(
            project_id=job.project_id,
            aggregate_id=job.id,
            kind="job.dispatch",
            payload={
                "job_id": job.id,
                "project_id": job.project_id,
                "task_name": TASK_NAME,
                "task_id": task_id,
                "queue": JOB_QUEUES[job.job_type],
            },
        )
    )
    db.flush()
    return attempt


def claim_job_attempt(db: Session, job_id: str, worker_name: str, project_id: str) -> JobAttempt | None:
    """Atomically transition a queued job and exactly one queued attempt to running.

    The conditional update is the concurrency guard.  A duplicate broker
    delivery, a second worker, or a cancellation that won the race all receive
    no claim and therefore cannot replace a terminal cancelled status.
    """
    now = utcnow()
    claimed_job_id = db.execute(
        update(Job)
        .where(Job.id == job_id, Job.project_id == project_id, Job.status == JobStatus.QUEUED)
        .values(status=JobStatus.RUNNING, started_at=now, current_stage="Initializing")
        .returning(Job.id)
    ).scalar_one_or_none()
    if claimed_job_id is None:
        return None

    attempt = db.scalar(
        select(JobAttempt)
        .where(JobAttempt.job_id == claimed_job_id, JobAttempt.status == JobStatus.QUEUED)
        .order_by(JobAttempt.attempt_number.desc())
        .limit(1)
    )
    if attempt is None:
        # This is a corrupted job state, not a second successful claim.  Keep
        # the transaction rollbackable for the worker rather than inventing an
        # attempt that might hide an accounting error.
        raise RuntimeError(f"Queued job {job_id} has no queued attempt")

    attempt.status = JobStatus.RUNNING
    attempt.worker_hostname = worker_name
    attempt.started_at = now
    db.flush()
    return attempt
