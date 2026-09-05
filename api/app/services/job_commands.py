"""Durable command creation and idempotent worker job claims."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models.job import Job, JobAttempt, JobStatus, JobType
from ..models.batch import Batch
from ..models.media import Mix
from ..models.outbox import OutboxMessage
from ..config import settings
from ..schemas.auth import CurrentPrincipal
from ..schemas.job import JobCreateRequest
from .metrics import record_counter


TASK_NAMES = {
    JobType.ANALYSIS: "tasks.run_analysis_pipeline",
    JobType.FINGERPRINT: "tasks.run_analysis_pipeline",
    JobType.MASTERING: "tasks.run_master_mix",
}

JOB_QUEUES = {
    JobType.ANALYSIS: "analysis-cpu",
    JobType.FINGERPRINT: "analysis-cpu",
    JobType.MASTERING: "dsp-heavy",
}


class UnsupportedJobTypeError(ValueError):
    """The API must not enqueue a type without a registered worker handler."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_job_dispatch(db: Session, job: Job, attempt_number: int) -> OutboxMessage:
    """Append the canonical durable broker command for an existing queued job."""
    task_id = f"job_{job.id}" if attempt_number == 1 else f"job_{job.id}_att_{attempt_number}"
    message = OutboxMessage(
        project_id=job.project_id,
        aggregate_id=job.id,
        kind="job.dispatch",
        payload={
            "job_id": job.id,
            "project_id": job.project_id,
            "attempt_number": attempt_number,
            "task_name": TASK_NAMES[job.job_type],
            "task_id": task_id,
            "queue": JOB_QUEUES[job.job_type],
        },
    )
    db.add(message)
    return message


def enqueue_job(db: Session, principal: CurrentPrincipal, mix: Mix, request: JobCreateRequest) -> Job:
    """Create a queued job, initial attempt, and broker command in one DB transaction.

    The caller owns the transaction boundary.  In particular, no broker call is
    made here: the outbox row cannot become visible without the matching job.
    """
    if mix.project_id != principal.project_id:
        raise PermissionError("Mix does not belong to the current project")

    job_type = JobType(request.job_type)
    if job_type not in TASK_NAMES:
        raise UnsupportedJobTypeError(f"Job type {job_type.value} is not supported by a registered worker")
    job = Job(
        id=str(uuid.uuid4()),
        mix_id=mix.id,
        project_id=principal.project_id,
        job_type=job_type,
        status=JobStatus.QUEUED,
        progress_percent=0.0,
        current_stage="Queued",
        parameters=request.parameters,
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
    enqueue_job_dispatch(db, job, attempt_number=1)
    db.flush()
    record_counter(
        "job.enqueued",
        tags={"job_type": job_type.value, "queue": JOB_QUEUES[job_type], "status": "queued"},
    )
    return job


def enqueue_retry(
    db: Session,
    job: Job,
    terminal_statuses: tuple[JobStatus, ...] = (JobStatus.FAILED, JobStatus.CANCELLED),
) -> JobAttempt | None:
    """Atomically requeue a terminal job and append exactly one dispatch command.

    The state transition is the retry claim. A stale or concurrent caller sees
    no returned row and must not manufacture another attempt/outbox command.
    """
    claimed_job_id = db.execute(
        update(Job)
        .where(
            Job.id == job.id,
            Job.project_id == job.project_id,
            Job.status.in_(terminal_statuses),
        )
        .values(
            status=JobStatus.QUEUED,
            progress_percent=0.0,
            current_stage="Re-queued",
            error_message=None,
            started_at=None,
            finished_at=None,
        )
        .returning(Job.id)
    ).scalar_one_or_none()
    if claimed_job_id is None:
        return None

    # The conditional transition above has claimed this job. Its batch parent
    # (when applicable) holds the sibling retry serialization lock, and the
    # job row itself protects ordinary single-job retry callers.
    attempt_number = (db.scalar(select(func.max(JobAttempt.attempt_number)).where(JobAttempt.job_id == job.id)) or 0) + 1
    attempt = JobAttempt(
        id=str(uuid.uuid4()),
        job_id=job.id,
        attempt_number=attempt_number,
        status=JobStatus.QUEUED,
    )
    db.add(attempt)
    db.refresh(job)
    enqueue_job_dispatch(db, job, attempt_number=attempt_number)
    db.flush()
    record_counter(
        "job.enqueued",
        tags={"job_type": job.job_type.value, "queue": JOB_QUEUES[job.job_type], "status": "queued"},
    )
    return attempt


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _attempt_query(job_id: str, attempt_number: int | None):
    query = select(JobAttempt).where(JobAttempt.job_id == job_id)
    if attempt_number is not None:
        query = query.where(JobAttempt.attempt_number == attempt_number)
    return query.order_by(JobAttempt.attempt_number.desc()).limit(1)


def claim_job_attempt(
    db: Session,
    job_id: str,
    worker_name: str,
    project_id: str,
    attempt_number: int | None = None,
    claim_token: str | None = None,
    now: datetime | None = None,
    lease_seconds: int | None = None,
) -> JobAttempt | None:
    """Claim a precise queued attempt or reclaim its expired fenced lease.

    Dispatches include their attempt number, so a delayed attempt-one broker
    delivery cannot acquire a newly queued attempt two.  A lease lets a Celery
    redelivery recover worker loss while the token fences the abandoned worker
    from updating the replacement claim.
    """
    current_time = now or utcnow()
    lease_duration = lease_seconds if lease_seconds is not None else settings.job_attempt_lease_seconds
    if lease_duration <= 0:
        raise ValueError("lease_seconds must be positive")
    token = claim_token or uuid.uuid4().hex
    if len(token) > 64:
        raise ValueError("claim token is too long")

    job = db.scalar(
        select(Job).where(Job.id == job_id, Job.project_id == project_id).with_for_update()
    )
    if job is None:
        return None

    is_reclaim = False
    if job.status is JobStatus.QUEUED:
        attempt = db.scalar(
            _attempt_query(job.id, attempt_number).where(JobAttempt.status == JobStatus.QUEUED)
        )
        if attempt is None:
            return None
        # A parent-row lock serializes sibling queued claims on PostgreSQL.
        if job.batch_id is not None:
            batch = db.scalar(
                select(Batch)
                .where(Batch.id == job.batch_id, Batch.project_id == project_id)
                .with_for_update()
            )
            if batch is None:
                raise RuntimeError(f"Batch {job.batch_id} for job {job_id} is outside project {project_id}")
            running_count = db.scalar(
                select(func.count()).select_from(Job).where(
                    Job.batch_id == batch.id,
                    Job.status == JobStatus.RUNNING,
                )
            )
            if running_count >= batch.max_parallelism:
                return None
        job.status = JobStatus.RUNNING
        job.started_at = current_time
        job.current_stage = "Initializing"
    elif job.status is JobStatus.RUNNING:
        attempt = db.scalar(
            _attempt_query(job.id, attempt_number).where(JobAttempt.status == JobStatus.RUNNING)
        )
        if attempt is None:
            return None
        lease_expires_at = _as_utc(attempt.lease_expires_at)
        # Old pre-lease rows must not be stolen merely because they predate the
        # migration; their owner remains authoritative until a heartbeat-aware
        # worker has established a lease.
        if lease_expires_at is None or lease_expires_at > current_time:
            return None
        is_reclaim = True
    else:
        return None

    attempt.status = JobStatus.RUNNING
    attempt.worker_hostname = worker_name
    attempt.claim_token = token
    attempt.started_at = current_time
    attempt.last_heartbeat_at = current_time
    attempt.lease_expires_at = current_time + timedelta(seconds=lease_duration)
    if is_reclaim:
        attempt.error_details = None

    if job.batch_id is not None:
        # Avoid a module import cycle at definition time: batch commands use
        # this module to create their children. The recompute shares this claim
        # transaction, so the stored parent cannot remain QUEUED after a child
        # commits RUNNING.
        from .batches import recompute_batch_status

        recompute_batch_status(db, job.batch_id)
    db.flush()
    return attempt


def heartbeat_job_attempt(
    db: Session,
    job_id: str,
    project_id: str,
    attempt_number: int,
    claim_token: str,
    *,
    now: datetime | None = None,
    lease_seconds: int | None = None,
) -> bool:
    """Extend only the active worker's lease; an old token is fenced out."""
    current_time = now or utcnow()
    lease_duration = lease_seconds if lease_seconds is not None else settings.job_attempt_lease_seconds
    result = db.execute(
        update(JobAttempt)
        .where(
            JobAttempt.job_id == job_id,
            JobAttempt.attempt_number == attempt_number,
            JobAttempt.status == JobStatus.RUNNING,
            JobAttempt.claim_token == claim_token,
            select(Job.id)
            .where(
                Job.id == JobAttempt.job_id,
                Job.project_id == project_id,
                Job.status == JobStatus.RUNNING,
            )
            .exists(),
        )
        .values(last_heartbeat_at=current_time, lease_expires_at=current_time + timedelta(seconds=lease_duration))
    )
    return result.rowcount == 1
