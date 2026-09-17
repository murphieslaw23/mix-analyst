"""Durable notification center + opt-in Web Push enrollment.

Terminal job outcomes create one in-app item each (deduplicated); Push
payloads carry only a notification id and safe deep link, never media
metadata. Actual Push delivery (VAPID send + retry/deactivation) is a
follow-up once provider credentials are configured.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models.notification import Notification, PushSubscription
from ...schemas.auth import CurrentPrincipal
from ...schemas.notification import (
    NotificationOut,
    PushSubscriptionIn,
    PushSubscriptionOut,
)
from ...services.notifications import dismiss as dismiss_notification_record
from ...services.notifications import mark_read as mark_notification_read_record
from ...services.push import subscription_endpoint_hash
from ..deps import get_current_principal, require_api_key

router = APIRouter()


def _owned_notification(
    db: Session, principal: CurrentPrincipal, notification_id: str
) -> Notification:
    row = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.project_id == principal.project_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    return row


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
):
    """List the caller's notification center items, newest first."""
    return (
        db.query(Notification)
        .filter(Notification.project_id == principal.project_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
):
    """Mark a center item as read (scoped; foreign ids 404)."""
    _owned_notification(db, principal, notification_id)
    return mark_notification_read_record(db, notification_id)


@router.post("/notifications/{notification_id}/dismiss", response_model=NotificationOut)
def dismiss_notification(
    notification_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
):
    """Dismiss a center item (scoped; foreign ids 404)."""
    _owned_notification(db, principal, notification_id)
    return dismiss_notification_record(db, notification_id)


@router.post(
    "/push/subscriptions",
    response_model=PushSubscriptionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_push_subscription(
    req: PushSubscriptionIn,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    _auth: Annotated[None, Depends(require_api_key)],
):
    """Enroll a browser Push endpoint (explicit opt-in only).

    One subscription per endpoint hash; re-enrollment reactivates.
    Only the hash is indexed — endpoint URLs and keys are payload data.
    """
    endpoint_hash = subscription_endpoint_hash(req.endpoint)
    existing = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint_hash == endpoint_hash)
        .first()
    )
    if existing:
        existing.project_id = principal.project_id
        existing.encrypted_payload = json.dumps(
            {"endpoint": req.endpoint, "keys": req.keys}
        )
        existing.deactivated_at = None
        db.commit()
        db.refresh(existing)
        return existing
    row = PushSubscription(
        project_id=principal.project_id,
        endpoint_hash=endpoint_hash,
        encrypted_payload=json.dumps({"endpoint": req.endpoint, "keys": req.keys}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete(
    "/push/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_push_subscription(
    subscription_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    _auth: Annotated[None, Depends(require_api_key)],
):
    """Remove a Push enrollment (unsubscribe / logout / deletion)."""
    row = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.id == subscription_id,
            PushSubscription.project_id == principal.project_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )
    db.delete(row)
    db.commit()
