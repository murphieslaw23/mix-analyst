"""Durable command creation and idempotent worker job claims."""

import threading
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings
from ..models.batch import Batch
from ..models.job import Job, JobAttempt, JobStatus, JobType
from ..models.media import Mix
from ..models.outbox import OutboxMessage
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

_lease_keeper_lock = threading.Lock()
_lease_keeper_keys: set[tuple[str, str, int, str]] = set()


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
    """Create a queued job, initial attempt, and broker command in one DB transaction."""
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
    """Atomically requeue a terminal job and append exactly one dispatch command."""
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


def _start_attempt_lease_keeper(
    bind,
    job_id: str,
    project_id: str,
    attempt_number: int,
    claim_token: str,
    lease_seconds: int,
) -> None:
    """Keep a live worker's exact fencing token leased during synchronous DSP."""
    key = (job_id, project_id, attempt_number, claim_token)
    with _lease_keeper_lock:
        if key in _lease_keeper_keys:
            return
        _lease_keeper_keys.add(key)

    interval = max(1.0, min(30.0, lease_seconds / 3.0))
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=bind)

    def run() -> None:
        try:
            while True:
                if threading.Event().wait(interval):
                    return
                heartbeat_db = session_factory()
                try:
                    alive = heartbeat_job_attempt(
                        heartbeat_db,
                        job_id,
                        project_id,
                        attempt_number,
                        claim_token,
                        lease_seconds=lease_seconds,
                        allow_expired=True,
                    )
                    if not alive:
                        heartbeat_db.rollback()
                        return
                    heartbeat_db.commit()
                except Exception:
                    heartbeat_db.rollback()
                    # A transient database outage must not kill the keeper. On
                    # recovery, the old token may renew only if no replacement
                    # has already claimed and changed the fencing token.
                finally:
                    heartbeat_db.close()
        finally:
            with _lease_keeper_lock:
                _lease_keeper_keys.discard(key)

    threading.Thread(target=run, name=f"job-lease-{job_id[:8]}", daemon=True).start()


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
    """Claim a precise queued attempt or reclaim its expired fenced lease."""
    current_time = now or utcnow()
    lease_duration = lease_seconds if lease_seconds is not None else settings.job_attempt_lease_seconds
    if lease_duration <= 0:
        raise ValueError("lease_seconds must be positive")
    token = claim_token or uuid.uuid4().hex
    if len(token) > 64:
        raise ValueError("claim token is too long")

    job = db.scalar(select(Job).where(Job.id == job_id, Job.project_id == project_id).with_for_update())
    if job is None:
        return None

    is_reclaim = False
    if job.status is JobStatus.QUEUED:
        attempt = db.scalar(_attempt_query(job.id, attempt_number).where(JobAttempt.status == JobStatus.QUEUED))
        if attempt is None:
            return None
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
        attempt = db.scalar(_attempt_query(job.id, attempt_number).where(JobAttempt.status == JobStatus.RUNNING))
        if attempt is None:
            return None
        lease_expires_at = _as_utc(attempt.lease_expires_at)
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
        from .batches import recompute_batch_status

        recompute_batch_status(db, job.batch_id)
    db.flush()

    # Production workers use PostgreSQL. SQLite is used by deterministic unit
    # tests and must not spawn background sessions against an ephemeral fixture.
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        _start_attempt_lease_keeper(
            bind,
            job_id,
            project_id,
            attempt.attempt_number,
            attempt.claim_token,
            lease_duration,
        )
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
    allow_expired: bool = False,
) -> bool:
    """Extend only the active worker's exact lease and fencing token."""
    current_time = now or utcnow()
    lease_duration = lease_seconds if lease_seconds is not None else settings.job_attempt_lease_seconds
    predicates = [
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
    ]
    if not allow_expired:
        predicates.append(JobAttempt.lease_expires_at > current_time)
    result = db.execute(
        update(JobAttempt)
        .where(*predicates)
        .values(last_heartbeat_at=current_time, lease_expires_at=current_time + timedelta(seconds=lease_duration))
    )
    return result.rowcount == 1
