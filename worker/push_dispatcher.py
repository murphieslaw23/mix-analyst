"""Privacy-safe Web Push delivery for durable notifications.

Loads a notification plus its project's active subscriptions, sends a
minimal routing payload (``version`` / ``notification_id`` / ``deep_link``
only) via pywebpush, and records per-subscription delivery outcomes:

- success -> ``"delivered"``
- HTTP 404/410 -> ``"deactivated"`` (endpoint gone; subscription retired)
- 429/5xx or transport failure -> ``"retryable"``, giving up to
  ``"deactivated"`` once attempts reach ``MAX_DELIVERY_ATTEMPTS``.

Each subscription commits independently so one failure never aborts the
rest of the batch. VAPID material comes from the environment only
(``VAPID_PRIVATE_KEY``, ``VAPID_CONTACT``); nothing secret ever enters a
payload.
"""

import json
import os
from collections.abc import Callable
from datetime import datetime, timezone

import pywebpush
from pywebpush import WebPushException
from sqlalchemy.orm import Session

from api.app.models.notification import Notification, PushSubscription
from api.app.services.push import build_push_payload, record_delivery

webpush = pywebpush.webpush
_ORIG_WEBPUSH = pywebpush.webpush

MAX_DELIVERY_ATTEMPTS = 5
MAX_ERROR_CHARS = 500
ALLOWED_PAYLOAD_KEYS = frozenset({"version", "notification_id", "deep_link"})
GONE_STATUS_CODES = frozenset({404, 410})


def _resolve_sender():
    """Return the active webpush sender.

    Module-level ``webpush`` stays patchable in tests
    (``monkeypatch.setattr(push_dispatcher, "webpush", fake)``) while a
    patch applied directly to ``pywebpush.webpush`` is honored too.
    """
    module_level = globals().get("webpush")
    if module_level is not None and module_level is not _ORIG_WEBPUSH:
        return module_level
    return pywebpush.webpush


def _status_code(exc: BaseException) -> int | None:
    """Extract an HTTP status from a push failure, any response shape."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status", None)
    if status is None:
        return None
    try:
        return int(status)
    except (TypeError, ValueError):
        return None


def _error_text(exc: BaseException) -> str:
    """Bounded one-line error description for the delivery ledger."""
    return f"{type(exc).__name__}: {exc}"[:MAX_ERROR_CHARS]


def _deactivate_subscription(db: Session, subscription_id: str) -> None:
    row = (
        db.query(PushSubscription)
        .filter(PushSubscription.id == subscription_id)
        .first()
    )
    if row is not None and row.deactivated_at is None:
        row.deactivated_at = datetime.now(timezone.utc)
        db.commit()


def _record_give_up_if_exhausted(db: Session, delivery, subscription_id: str) -> bool:
    """Flip an exhausted retryable delivery to deactivated.

    Returns True when the subscription was given up on (delivery marked
    ``"deactivated"`` and the subscription retired so later runs skip it).
    """
    if delivery.attempts >= MAX_DELIVERY_ATTEMPTS:
        delivery.status = "deactivated"
        db.commit()
        _deactivate_subscription(db, subscription_id)
        return True
    return False


def _record_retryable(
    db: Session, notification_id: str, subscription_id: str, error: str
):
    """Record a transient failure, giving up once attempts are exhausted."""
    delivery = record_delivery(db, notification_id, subscription_id, "retryable", error)
    return delivery


def deliver_notification(
    db_session_factory: Callable[[], Session], notification_id: str
) -> dict:
    """Deliver one notification to its project's active Push subscriptions.

    Returns a summary dict with ``status`` (``delivered`` | ``retryable`` |
    ``deactivated`` | ``no_subscriptions`` | ``misconfigured``),
    ``attempted`` (active subscriptions tried), and ``delivered``
    (subscriptions that accepted the push).
    """
    vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY")
    if not vapid_private_key:
        return {"status": "misconfigured", "attempted": 0, "delivered": 0}
    vapid_contact = os.environ.get("VAPID_CONTACT", "mailto:admin@example.com")

    db = db_session_factory()
    try:
        notification = (
            db.query(Notification).filter(Notification.id == notification_id).first()
        )
        if notification is None:
            return {"status": "no_subscriptions", "attempted": 0, "delivered": 0}
        payload = build_push_payload(notification)
        assert set(payload.keys()) == set(ALLOWED_PAYLOAD_KEYS), (
            f"refusing to send push payload with unexpected keys: {sorted(payload)}"
        )
        data = json.dumps(payload)
        project_id = notification.project_id

        subscriptions = (
            db.query(PushSubscription)
            .filter(
                PushSubscription.project_id == project_id,
                PushSubscription.deactivated_at.is_(None),
            )
            .all()
        )
        if not subscriptions:
            return {"status": "no_subscriptions", "attempted": 0, "delivered": 0}
        # Snapshot before any per-subscription commit expires ORM state.
        targets = [(s.id, s.encrypted_payload) for s in subscriptions]

        sender = _resolve_sender()
        attempted = len(targets)
        delivered = 0
        retryable = 0
        deactivated = 0
        for subscription_id, encrypted_payload in targets:
            try:
                try:
                    subscription_info = json.loads(encrypted_payload)
                except (TypeError, ValueError) as e:
                    delivery = _record_retryable(
                        db, notification_id, subscription_id, _error_text(e)
                    )
                    if _record_give_up_if_exhausted(db, delivery, subscription_id):
                        deactivated += 1
                    else:
                        retryable += 1
                    continue
                try:
                    sender(
                        subscription_info=subscription_info,
                        data=data,
                        vapid_private_key=vapid_private_key,
                        vapid_claims={"sub": vapid_contact},
                    )
                except WebPushException as e:
                    error = _error_text(e)
                    if _status_code(e) in GONE_STATUS_CODES:
                        record_delivery(
                            db,
                            notification_id,
                            subscription_id,
                            "deactivated",
                            error,
                        )
                        _deactivate_subscription(db, subscription_id)
                        deactivated += 1
                    else:
                        delivery = _record_retryable(
                            db, notification_id, subscription_id, error
                        )
                        if _record_give_up_if_exhausted(db, delivery, subscription_id):
                            deactivated += 1
                        else:
                            retryable += 1
                except Exception as e:  # noqa: BLE001 - transport failure stays retryable
                    delivery = _record_retryable(
                        db, notification_id, subscription_id, _error_text(e)
                    )
                    if _record_give_up_if_exhausted(db, delivery, subscription_id):
                        deactivated += 1
                    else:
                        retryable += 1
                else:
                    record_delivery(db, notification_id, subscription_id, "delivered")
                    delivered += 1
            except Exception:  # noqa: BLE001 - bookkeeping must not abort siblings
                # Bookkeeping must never abort sibling subscriptions.
                db.rollback()
                retryable += 1

        if retryable > 0:
            status = "retryable"
        elif delivered > 0:
            status = "delivered"
        else:
            status = "deactivated"
        return {"status": status, "attempted": attempted, "delivered": delivered}
    finally:
        db.close()
