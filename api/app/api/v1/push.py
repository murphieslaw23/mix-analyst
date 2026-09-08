"""Authenticated Web Push enrollment and deactivation routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...api.deps import get_current_principal
from ...config import settings
from ...db.session import get_db
from ...models.push_subscription import PushSubscription
from ...schemas.auth import CurrentPrincipal
from ...schemas.push import PushConfigOut, PushSubscriptionIn, PushSubscriptionOut
from ...services.push import create_push_subscription

router = APIRouter()


@router.get("/push/config", response_model=PushConfigOut)
def push_config(
    _: CurrentPrincipal = Depends(get_current_principal),
) -> PushConfigOut:
    public_key = settings.vapid_public_key or None
    return PushConfigOut(enabled=bool(public_key), vapid_public_key=public_key)


def _store_subscription(
    payload: PushSubscriptionIn,
    db: Session,
    principal: CurrentPrincipal,
) -> PushSubscription:
    try:
        subscription = create_push_subscription(
            db,
            user_id=principal.user_id,
            project_id=principal.project_id,
            subscription_json=payload.model_dump(by_alias=True),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    db.commit()
    db.refresh(subscription)
    return subscription


@router.post(
    "/push/subscriptions",
    response_model=PushSubscriptionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription(
    payload: PushSubscriptionIn,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> PushSubscription:
    return _store_subscription(payload, db, principal)


@router.post("/push/subscriptions/refresh", response_model=PushSubscriptionOut)
def refresh_subscription(
    payload: PushSubscriptionIn,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> PushSubscription:
    return _store_subscription(payload, db, principal)


@router.delete(
    "/push/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> Response:
    subscription = db.scalar(
        select(PushSubscription).where(
            PushSubscription.id == subscription_id,
            PushSubscription.project_id == principal.project_id,
            PushSubscription.user_id == principal.user_id,
        )
    )
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Push subscription not found",
        )
    if subscription.active:
        subscription.active = False
        subscription.deactivated_at = datetime.now(timezone.utc)
        subscription.updated_at = subscription.deactivated_at
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
