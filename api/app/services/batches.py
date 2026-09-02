"""Durable batch command handling and child-derived aggregate state."""

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.batch import Batch, BatchStatus
from ..models.job import Job, JobStatus, JobType
from ..models.media import Mix
from ..schemas.auth import CurrentPrincipal
from ..schemas.batch import BatchCreateRequest
from ..schemas.job import JobCreateRequest
from .job_commands import enqueue_job, enqueue_job_dispatch, enqueue_retry


def _status_counts(counts: Iterable[tuple[JobStatus, int]]) -> dict[JobStatus, int]:
    result = {status: 0 for status in JobStatus}
    for status, count in counts:
        result[JobStatus(status)] = count
    return result


def apply_counts_to_batch(batch: Batch, counts: Iterable[tuple[JobStatus, int]]) -> Batch:
    """Apply a complete persisted-child snapshot, never an incremental counter."""
    by_status = _status_counts(counts)
    total = sum(by_status.values())
    completed = by_status[JobStatus.SUCCEEDED]
    failed = by_status[JobStatus.FAILED]
    cancelled = by_status[JobStatus.CANCELLED]
    active = by_status[JobStatus.QUEUED] + by_status[JobStatus.RUNNING]

    batch.total_count = total
    batch.completed_count = completed
    batch.failed_count = failed
    batch.cancelled_count = cancelled
    if by_status[JobStatus.RUNNING]:
        batch.status = BatchStatus.RUNNING
    elif by_status[JobStatus.QUEUED]:
        batch.status = BatchStatus.QUEUED
    elif completed == total:
        batch.status = BatchStatus.SUCCEEDED
    elif completed and (failed or cancelled):
        batch.status = BatchStatus.PARTIAL_FAILED
    elif failed:
        batch.status = BatchStatus.FAILED
    elif cancelled == total:
        batch.status = BatchStatus.CANCELLED
    elif active:
        batch.status = BatchStatus.RUNNING
    else:
        # Empty batches are not creatable, but retain a safe state if an old
        # parent is inspected after manual child cleanup.
        batch.status = BatchStatus.CANCELLED
    return batch


def recompute_batch_status(db: Session, batch_id: str) -> Batch:
    """Refresh a batch read model solely from its persisted child job states."""
    # API and worker sessions intentionally disable autoflush in some
    # environments; make all just-created/changed children visible first.
    db.flush()
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise LookupError(f"Batch {batch_id} was not found")
    counts = db.execute(
        select(Job.status, func.count())
        .where(Job.batch_id == batch_id)
        .group_by(Job.status)
    ).all()
    apply_counts_to_batch(batch, counts)
    db.flush()
    return batch


def create_batch(db: Session, principal: CurrentPrincipal, request: BatchCreateRequest) -> Batch:
    """Create one batch and one durable outbox-backed mastering command per mix."""
    mix_ids = list(dict.fromkeys(request.mix_ids))
    if len(mix_ids) != len(request.mix_ids):
        raise ValueError("Each mix can appear only once in a batch")
    mixes = db.scalars(
        select(Mix)
        .where(Mix.project_id == principal.project_id, Mix.id.in_(mix_ids))
        .order_by(Mix.created_at, Mix.id)
    ).all()
    by_id = {mix.id: mix for mix in mixes}
    if len(by_id) != len(mix_ids):
        raise PermissionError("One or more mixes do not belong to the current project")

    batch = Batch(project_id=principal.project_id, preset=request.preset, max_parallelism=request.max_parallelism)
    db.add(batch)
    db.flush()
    parameters = {
        "target_lufs": -9.0,
        "true_peak_dbtp": -1.0,
        "algorithm_version": "v1",
        **request.preset,
    }
    for mix_id in mix_ids:
        child = enqueue_job(
            db,
            principal,
            by_id[mix_id],
            JobCreateRequest(job_type=JobType.MASTERING, parameters=parameters),
        )
        child.batch_id = batch.id
    recompute_batch_status(db, batch.id)
    return batch


def retry_batch_items(db: Session, batch: Batch, job_ids: list[str]) -> Batch:
    """Retry selected failed children in place, retaining successful child rows/artifacts."""
    unique_ids = list(dict.fromkeys(job_ids))
    if len(unique_ids) != len(job_ids):
        raise ValueError("Each batch job can be selected only once")
    # Lock the owner-scoped parent first, then its selected children. The parent
    # gives all retry requests for this batch one serialization point; locks on
    # the rows make the selection explicit for databases with row locking.
    locked_batch = db.scalar(
        select(Batch)
        .where(Batch.id == batch.id, Batch.project_id == batch.project_id)
        .with_for_update()
    )
    if locked_batch is None:
        raise PermissionError("Batch does not belong to the current project")
    children = db.scalars(
        select(Job)
        .where(Job.batch_id == locked_batch.id, Job.project_id == locked_batch.project_id, Job.id.in_(unique_ids))
        .with_for_update()
    ).all()
    if len(children) != len(unique_ids):
        raise PermissionError("One or more jobs do not belong to this batch")
    for child in children:
        if child.status is not JobStatus.FAILED:
            raise ValueError("Only failed batch jobs can be retried")
    for child in children:
        if enqueue_retry(db, child, terminal_statuses=(JobStatus.FAILED,)) is None:
            raise ValueError("Only failed batch jobs can be retried")
    return recompute_batch_status(db, locked_batch.id)


def advance_batch_after_terminal_job(db: Session, job_id: str, project_id: str) -> None:
    """Durably redeliver one waiting child after a batch slot becomes free.

    Initial children are all created through ``enqueue_job``. A worker that
    received a child while the cap was full returns without claiming it; this
    follow-up uses that same outbox command representation so it can be
    delivered again after a sibling reaches a terminal state.
    """
    job = db.scalar(select(Job).where(Job.id == job_id, Job.project_id == project_id))
    if job is None or job.batch_id is None:
        return
    batch = db.scalar(
        select(Batch)
        .where(Batch.id == job.batch_id, Batch.project_id == project_id)
        .with_for_update()
    )
    if batch is None:
        raise RuntimeError(f"Batch {job.batch_id} is outside project {project_id}")
    recompute_batch_status(db, batch.id)
    running_count = db.scalar(
        select(func.count()).select_from(Job).where(
            Job.batch_id == batch.id,
            Job.status == JobStatus.RUNNING,
        )
    )
    if running_count >= batch.max_parallelism:
        return
    queued_job = db.scalar(
        select(Job)
        .where(
            Job.batch_id == batch.id,
            Job.project_id == project_id,
            Job.status == JobStatus.QUEUED,
        )
        .order_by(Job.created_at, Job.id)
        .limit(1)
    )
    if queued_job is not None:
        enqueue_job_dispatch(db, queued_job, attempt_number=1)
