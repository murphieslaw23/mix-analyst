"""Transactional creation and state changes for notification-center rows."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.identity import Project
from ..models.job import Job, JobStatus
from ..models.notification import Notification

_TERMINAL_KINDS: dict[JobStatus, str] = {
    JobStatus.SUCCEEDED: "job.succeeded",
    JobStatus.FAILED: "job.failed",
    JobStatus.CANCELLED: "job.cancelled",
}


def notification_kind_for_terminal_job(job: Job) -> str:
    try:
        return _TERMINAL_KINDS[job.status]
    except KeyError as exc:
        raise ValueError("Notifications are only created for terminal jobs") from exc


def _notification_copy(kind: str, job: Job) -> tuple[str, str]:
    job_label = job.job_type.value.lower().replace("_", " ").title()
    if kind == "job.succeeded":
        return f"{job_label} complete", "Your finished audio is ready in the Library."
    if kind == "job.failed":
        return (
            f"{job_label} needs attention",
            "Processing stopped. Review the job and retry when you are ready.",
        )
    if kind == "job.cancelled":
        return (
            f"{job_label} cancelled",
            "This job was cancelled before a result was published.",
        )
    raise ValueError("Unsupported notification kind")


def create_job_notification(
    db: Session, job: Job, kind: str | None = None
) -> Notification:
    """Create exactly one durable item for a terminal job outcome.

    This function only flushes. Its caller owns the surrounding terminal job
    transaction, so a committed notification always has a committed terminal
    state/event and a rolled-back job has no stray user-facing item.
    """
    expected_kind = notification_kind_for_terminal_job(job)
    if kind is not None and kind != expected_kind:
        raise ValueError("Notification kind does not match the terminal job state")
    kind = expected_kind
    dedupe_key = f"{kind}:{job.id}"
    existing = db.scalar(
        select(Notification).where(Notification.dedupe_key == dedupe_key)
    )
    if existing is not None:
        return existing

    owner_id = db.scalar(select(Project.owner_id).where(Project.id == job.project_id))
    if owner_id is None:
        raise RuntimeError(f"Terminal job {job.id} has no owning project")
    title, body = _notification_copy(kind, job)
    notification = Notification(
        project_id=job.project_id,
        user_id=owner_id,
        job_id=job.id,
        kind=kind,
        dedupe_key=dedupe_key,
        title=title,
        body=body,
        deep_link=f"/jobs/{job.id}",
    )
    try:
        # The savepoint preserves the terminal transaction if another worker
        # wins the unique-key race between the lookup and insert.
        with db.begin_nested():
            db.add(notification)
            db.flush()
        return notification
    except IntegrityError:
        existing = db.scalar(
            select(Notification).where(Notification.dedupe_key == dedupe_key)
        )
        if existing is None:
            raise
        return existing


def mark_notification_read(db: Session, notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.flush()
    return notification


def dismiss_notification(db: Session, notification: Notification) -> Notification:
    if notification.dismissed_at is None:
        notification.dismissed_at = datetime.now(timezone.utc)
        db.flush()
    return notification
