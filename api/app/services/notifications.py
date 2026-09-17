from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.notification import Notification


def create_job_notification(
    db: Session,
    *,
    project_id: str,
    job_id: str | None,
    kind: str,
    deep_link: str,
) -> Notification:
    """Get-or-create a job notification keyed by ``kind:job_id``."""
    dedupe_key = f"{kind}:{job_id}"
    existing = (
        db.query(Notification).filter(Notification.dedupe_key == dedupe_key).first()
    )
    if existing is not None:
        return existing
    notification = Notification(
        project_id=project_id,
        job_id=job_id,
        kind=kind,
        dedupe_key=dedupe_key,
        deep_link=deep_link,
        status="unread",
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def mark_read(db: Session, id: str) -> Notification:
    """Mark a notification as read."""
    notification = db.query(Notification).filter(Notification.id == id).first()
    if notification is None:
        raise ValueError(f"Notification not found: {id}")
    notification.status = "read"
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)
    return notification


def dismiss(db: Session, id: str) -> Notification:
    """Dismiss a notification."""
    notification = db.query(Notification).filter(Notification.id == id).first()
    if notification is None:
        raise ValueError(f"Notification not found: {id}")
    notification.status = "dismissed"
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)
    return notification
