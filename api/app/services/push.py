"""Encrypted subscription persistence and bounded, privacy-safe Web Push delivery."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models.notification import Notification
from ..models.push_subscription import PushDelivery, PushSubscription

MAX_DELIVERY_ATTEMPTS = 4
_SAFE_JOB_LINK = re.compile(r"^/jobs/[A-Za-z0-9_-]+$")


class PushDeliveryError(Exception):
    def __init__(self, *, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


class PushSender(Protocol):
    def __call__(
        self,
        *,
        subscription_info: dict[str, Any],
        payload: dict[str, object],
    ) -> None: ...


@dataclass(frozen=True)
class DeliveryOutcome:
    status: str
    attempted: int = 0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _encryption_secret() -> str:
    return settings.push_encryption_key or settings.auth_jwt_secret


def _fernet() -> Fernet:
    digest = hashlib.sha256(
        f"mix-analyst:web-push:{_encryption_secret()}".encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _canonical_subscription(subscription_json: dict[str, Any]) -> dict[str, Any]:
    endpoint = subscription_json.get("endpoint")
    keys = subscription_json.get("keys")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        raise ValueError("Push endpoint must use HTTPS")
    if not isinstance(keys, dict):
        raise TypeError("Push subscription keys are required")
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")
    if not isinstance(p256dh, str) or not p256dh:
        raise ValueError("Push subscription p256dh key is required")
    if not isinstance(auth, str) or not auth:
        raise ValueError("Push subscription auth key is required")
    return {
        "endpoint": endpoint,
        "expirationTime": subscription_json.get("expirationTime"),
        "keys": {"p256dh": p256dh, "auth": auth},
    }


def create_push_subscription(
    db: Session,
    *,
    user_id: str,
    project_id: str,
    subscription_json: dict[str, Any],
) -> PushSubscription:
    canonical = _canonical_subscription(subscription_json)
    endpoint_hash = hashlib.sha256(canonical["endpoint"].encode()).hexdigest()
    encrypted_payload = _fernet().encrypt(
        json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode()
    ).decode("ascii")

    existing = db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint_hash == endpoint_hash
        )
    )
    if existing is not None:
        if existing.user_id != user_id or existing.project_id != project_id:
            raise ValueError("Push endpoint is already registered to another principal")
        existing.encrypted_payload = encrypted_payload
        existing.active = True
        existing.deactivated_at = None
        existing.updated_at = _utcnow()
        db.flush()
        return existing

    subscription = PushSubscription(
        user_id=user_id,
        project_id=project_id,
        endpoint_hash=endpoint_hash,
        encrypted_payload=encrypted_payload,
    )
    db.add(subscription)
    db.flush()
    return subscription


def decrypt_push_subscription(subscription: PushSubscription) -> dict[str, Any]:
    payload = _fernet().decrypt(subscription.encrypted_payload.encode("ascii"))
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError("Stored Push subscription is invalid")
    return value


def queue_notification_deliveries(db: Session, notification: Notification) -> int:
    subscriptions = list(
        db.scalars(
            select(PushSubscription).where(
                PushSubscription.project_id == notification.project_id,
                PushSubscription.user_id == notification.user_id,
                PushSubscription.active.is_(True),
            )
        )
    )
    created = 0
    for subscription in subscriptions:
        existing = db.scalar(
            select(PushDelivery).where(
                PushDelivery.notification_id == notification.id,
                PushDelivery.subscription_id == subscription.id,
            )
        )
        if existing is not None:
            continue
        delivery = PushDelivery(
            notification_id=notification.id,
            subscription_id=subscription.id,
            status="pending",
        )
        try:
            with db.begin_nested():
                db.add(delivery)
                db.flush()
            created += 1
        except IntegrityError:
            # Another terminal worker may have won the unique pair race.
            pass
    return created


def _safe_deep_link(path: str) -> str:
    if path == "/more/notifications" or _SAFE_JOB_LINK.fullmatch(path):
        return path
    return "/more/notifications"


def _os_payload(notification: Notification) -> dict[str, object]:
    return {
        "version": 1,
        "notification_id": notification.id,
        "deep_link": _safe_deep_link(notification.deep_link),
    }


def _default_sender(
    *, subscription_info: dict[str, Any], payload: dict[str, object]
) -> None:
    from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload, separators=(",", ":")),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_contact},
            ttl=300,
        )
    except WebPushException as exc:
        response = getattr(exc, "response", None)
        status_code = int(getattr(response, "status_code", 503) or 503)
        raise PushDeliveryError(
            status_code=status_code,
            message=f"Push provider returned HTTP {status_code}",
        ) from exc


def _is_due(value: datetime | None, now: datetime) -> bool:
    if value is None:
        return True
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= now


def deliver_notification(
    notification_id: str,
    *,
    db: Session,
    sender: PushSender | None = None,
) -> DeliveryOutcome:
    notification = db.get(Notification, notification_id)
    if notification is None:
        return DeliveryOutcome(status="missing")

    if sender is None:
        if not settings.vapid_private_key or not settings.vapid_contact:
            return DeliveryOutcome(status="not_configured")
        sender = _default_sender

    now = _utcnow()
    deliveries = list(
        db.scalars(
            select(PushDelivery)
            .where(
                PushDelivery.notification_id == notification_id,
                PushDelivery.status.in_(("pending", "retry")),
            )
            .order_by(PushDelivery.created_at, PushDelivery.id)
        )
    )
    if not deliveries:
        return DeliveryOutcome(status="idle")

    attempted = 0
    statuses: list[str] = []
    for delivery in deliveries:
        if not _is_due(delivery.next_attempt_at, now):
            continue
        subscription = db.get(PushSubscription, delivery.subscription_id)
        if subscription is None or not subscription.active:
            delivery.status = "deactivated"
            delivery.updated_at = now
            statuses.append("deactivated")
            continue

        delivery.attempt_count += 1
        attempted += 1
        delivery.next_attempt_at = None
        delivery.updated_at = now
        try:
            sender(
                subscription_info=decrypt_push_subscription(subscription),
                payload=_os_payload(notification),
            )
        except PushDeliveryError as exc:
            delivery.last_status_code = exc.status_code
            if exc.status_code in {404, 410}:
                subscription.active = False
                subscription.deactivated_at = now
                subscription.updated_at = now
                delivery.status = "deactivated"
            elif exc.status_code == 429 or exc.status_code >= 500:
                if delivery.attempt_count < MAX_DELIVERY_ATTEMPTS:
                    delivery.status = "retry"
                    delay_seconds = 30 * (2 ** (delivery.attempt_count - 1))
                    delivery.next_attempt_at = now + timedelta(seconds=delay_seconds)
                else:
                    delivery.status = "failed"
            else:
                delivery.status = "failed"
            statuses.append(delivery.status)
        else:
            delivery.status = "delivered"
            delivery.delivered_at = now
            delivery.last_status_code = None
            statuses.append("delivered")

    db.flush()
    if not statuses:
        return DeliveryOutcome(status="idle", attempted=attempted)
    if "retry" in statuses:
        status = "retry"
    elif "failed" in statuses:
        status = "failed"
    elif "delivered" in statuses:
        status = "delivered"
    else:
        status = "deactivated"
    return DeliveryOutcome(status=status, attempted=attempted)
