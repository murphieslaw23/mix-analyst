"""Owner-scoped routes for the durable in-app notification center."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...api.deps import get_current_principal
from ...db.session import get_db
from ...models.notification import Notification
from ...schemas.auth import CurrentPrincipal
from ...schemas.notification import NotificationListResponse, NotificationOut
from ...services.notifications import dismiss_notification, mark_notification_read

router = APIRouter()


def _owned_notification(
    db: Session, principal: CurrentPrincipal, notification_id: str
) -> Notification:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.project_id == principal.project_id,
            Notification.user_id == principal.user_id,
        )
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    return notification


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    include_dismissed: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    scoped = select(Notification).where(
        Notification.project_id == principal.project_id,
        Notification.user_id == principal.user_id,
    )
    if not include_dismissed:
        scoped = scoped.where(Notification.dismissed_at.is_(None))
    total = db.scalar(select(func.count()).select_from(scoped.subquery())) or 0
    items = list(
        db.scalars(
            scoped.order_by(
                Notification.created_at.desc(), Notification.id.desc()
            ).limit(limit)
        )
    )
    return NotificationListResponse(items=items, total=total)


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def read_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    notification = mark_notification_read(
        db, _owned_notification(db, principal, notification_id)
    )
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/notifications/{notification_id}/dismiss", response_model=NotificationOut)
def dismiss_notification_route(
    notification_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    notification = dismiss_notification(
        db, _owned_notification(db, principal, notification_id)
    )
    db.commit()
    db.refresh(notification)
    return notification
