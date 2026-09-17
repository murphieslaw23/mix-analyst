"""Durable job commands: outbox-backed enqueue plus atomic worker claims.

Queueing occurs only through committed outbox records — the job, its
first attempt, and the dispatch command land in a single transaction, so
a broker failure can never lose a queued job. Workers claim attempts
atomically and terminal transitions never overwrite a cancellation.
"""

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models.job import Job, JobAttempt, JobStatus, JobType
from ..models.outbox import OutboxMessage

# sender(task_name, args, task_id, queue) -> broker task id
TaskSender = Callable[[str, list[Any], str, str], str]


def enqueue_job(
    db: Session,
    *,
    mix_id: str,
    job_type: JobType,
    task_name: str,
    task_args: list[Any] | Callable[[str], list[Any]],
    queue: str,
    sender: TaskSender | None = None,
) -> Job:
    """Persist Job + attempt + outbox dispatch in one transaction.

    If `sender` is given, one inline delivery is attempted immediately;
    broker failures leave the job QUEUED with a retryable outbox row
    instead of failing the request.
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
    args = task_args(job.id) if callable(task_args) else task_args
    db.add(
        OutboxMessage(
            id=str(uuid.uuid4()),
            aggregate_id=job.id,
            kind="job.dispatch",
            payload=json.dumps(
                {
                    "task_name": task_name,
                    "args": args,
                    "task_id": f"job_{job.id}",
                    "queue": queue,
                }
            ),
        )
    )
    db.commit()
    db.refresh(job)

    if sender is not None:
        from worker.outbox_dispatcher import dispatch_pending

        dispatch_pending(db, sender, job_ids=[job.id])

    db.refresh(job)
    return job


def claim_queued_job(db: Session, job_id: str, worker_hostname: str) -> bool:
    """Atomically move one QUEUED job to RUNNING.

    Returns True exactly once per job — concurrent workers racing the
    same row get False. Cancelled or finished jobs are never claimed.
    """
    now = datetime.now(timezone.utc)
    claimed = (
        db.query(Job)
        .filter(Job.id == job_id, Job.status == JobStatus.QUEUED)
        .update(
            {
                Job.status: JobStatus.RUNNING,
                Job.started_at: now,
                Job.current_stage: "Claimed by worker",
            },
            synchronize_session=False,
        )
    )
    if claimed != 1:
        db.rollback()
        return False
    db.query(JobAttempt).filter(
        JobAttempt.job_id == job_id, JobAttempt.status == JobStatus.QUEUED
    ).update(
        {
            JobAttempt.status: JobStatus.RUNNING,
            JobAttempt.worker_hostname: worker_hostname,
        },
        synchronize_session=False,
    )
    db.commit()
    return True


def complete_job_attempt(
    db: Session,
    job_id: str,
    *,
    ok: bool,
    error: str | None = None,
) -> bool:
    """Record a terminal outcome without clobbering terminal state.

    Success requires a claimed (RUNNING) job; failure may also land from
    QUEUED (e.g. missing audio before the claim). Returns False — leaving
    the row untouched — when the job is already terminal, so in particular
    a late worker can never overwrite a cancellation.
    """
    now = datetime.now(timezone.utc)
    final = JobStatus.SUCCEEDED if ok else JobStatus.FAILED
    scope = [JobStatus.RUNNING] if ok else [JobStatus.QUEUED, JobStatus.RUNNING]
    updated = (
        db.query(Job)
        .filter(Job.id == job_id, Job.status.in_(scope))
        .update(
            {
                Job.status: final,
                Job.progress_percent: 100.0 if ok else 0.0,
                Job.current_stage: "Complete" if ok else "Failed",
                Job.error_message: error,
                Job.finished_at: now,
            },
            synchronize_session=False,
        )
    )
    if updated != 1:
        db.rollback()
        return False
    db.query(JobAttempt).filter(
        JobAttempt.job_id == job_id,
        JobAttempt.status.in_([JobStatus.RUNNING, JobStatus.QUEUED]),
    ).update(
        {JobAttempt.status: final, JobAttempt.finished_at: now},
        synchronize_session=False,
    )
    db.commit()
    return True
