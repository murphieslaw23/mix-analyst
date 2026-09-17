"""Persistent batch fan-out: one Batch parent with ANALYSIS child jobs.

Child jobs travel the same transactional outbox path as single jobs, so a
broker failure never loses a queued child. The batch status is a pure
aggregate derived solely from persistent child rows.
"""

import json
import uuid

from sqlalchemy.orm import Session

from ..models.batch import Batch
from ..models.job import Job, JobStatus, JobType
from ..models.media import Mix
from ..models.outbox import OutboxMessage
from .job_commands import TaskSender, enqueue_job


def create_batch(
    db: Session,
    *,
    project_id: str,
    mix_ids: list[str],
    sender: TaskSender | None = None,
) -> Batch:
    """Verify owned mixes, then fan out one ANALYSIS child job per mix."""
    for mix_id in mix_ids:
        owned = (
            db.query(Mix).filter(Mix.id == mix_id, Mix.project_id == project_id).first()
        )
        if owned is None:
            raise ValueError(f"Mix not found: {mix_id}")

    batch = Batch(
        id=str(uuid.uuid4()),
        project_id=project_id,
        status="QUEUED",
        total_count=0,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    for mix_id in mix_ids:
        job = enqueue_job(
            db,
            mix_id=mix_id,
            project_id=project_id,
            job_type=JobType.ANALYSIS,
            task_name="tasks.run_analysis_pipeline",
            task_args=lambda jid: [jid],
            queue="analysis",
            sender=sender,
        )
        job.batch_id = batch.id
        db.commit()

    batch.total_count = len(mix_ids)
    db.commit()
    db.refresh(batch)
    return batch


def recompute_batch_status(db: Session, batch: Batch) -> str:
    """Derive batch status solely from persistent child job rows."""
    children: list[Job] = db.query(Job).filter(Job.batch_id == batch.id).all()
    if not children:
        status = "QUEUED"
    else:
        statuses: list[JobStatus] = [child.status for child in children]
        has_running = any(s == JobStatus.RUNNING for s in statuses)
        has_queued = any(s == JobStatus.QUEUED for s in statuses)
        n_succeeded = sum(1 for s in statuses if s == JobStatus.SUCCEEDED)
        n_failed = sum(1 for s in statuses if s == JobStatus.FAILED)
        n_cancelled = sum(1 for s in statuses if s == JobStatus.CANCELLED)
        total = len(statuses)
        if has_running:
            status = "RUNNING"
        elif has_queued:
            status = "QUEUED"
        elif n_succeeded == total:
            status = "SUCCEEDED"
        elif n_failed == total:
            status = "FAILED"
        elif n_cancelled == total:
            status = "CANCELLED"
        else:
            status = "PARTIAL_FAILED"
    batch.status = status
    db.commit()
    db.refresh(batch)
    return status


def retry_failed_items(
    db: Session,
    batch: Batch,
    sender: TaskSender | None = None,
) -> int:
    """Re-queue every FAILED child; successful children are untouched."""
    failed: list[Job] = (
        db.query(Job)
        .filter(Job.batch_id == batch.id, Job.status == JobStatus.FAILED)
        .all()
    )
    for job in failed:
        job.status = JobStatus.QUEUED
        job.progress_percent = 0.0
        job.current_stage = "Re-queued"
        job.error_message = None
        job.finished_at = None
        db.add(
            OutboxMessage(
                id=str(uuid.uuid4()),
                aggregate_id=job.id,
                kind="job.dispatch",
                payload=json.dumps(
                    {
                        "task_name": "tasks.run_analysis_pipeline",
                        "args": [job.id],
                        "task_id": f"job_{job.id}",
                        "queue": "analysis",
                    }
                ),
            )
        )
    db.commit()

    if sender is not None and failed:
        from worker.outbox_dispatcher import dispatch_pending

        dispatch_pending(db, sender, job_ids=[job.id for job in failed])

    recompute_batch_status(db, batch)
    return len(failed)
