import hashlib

from sqlalchemy.orm import Session

from ..models.notification import Notification, NotificationDelivery


def build_push_payload(notification: Notification) -> dict:
    """Build a privacy-safe push payload with only routing fields."""
    return {
        "version": 1,
        "notification_id": notification.id,
        "deep_link": notification.deep_link,
    }


def subscription_endpoint_hash(endpoint: str) -> str:
    """Return the stable sha256 hex digest for a push endpoint."""
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def record_delivery(
    db: Session,
    notification_id: str,
    subscription_id: str,
    status: str,
    error: str | None = None,
) -> NotificationDelivery:
    """Upsert a single delivery row per (notification, subscription) pair."""
    existing = (
        db.query(NotificationDelivery)
        .filter(
            NotificationDelivery.notification_id == notification_id,
            NotificationDelivery.subscription_id == subscription_id,
        )
        .first()
    )
    if existing is not None:
        existing.status = status
        existing.last_error = error
        existing.attempts = (existing.attempts or 0) + 1
        db.commit()
        db.refresh(existing)
        return existing
    delivery = NotificationDelivery(
        notification_id=notification_id,
        subscription_id=subscription_id,
        status=status,
        attempts=1,
        last_error=error,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery
