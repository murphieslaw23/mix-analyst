"""Encrypted Web Push subscriptions and idempotent delivery records."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from ..db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("endpoint_hash", name="uq_push_subscriptions_endpoint_hash"),
    )

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: str = Column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    user_id: str = Column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    endpoint_hash: str = Column(String(64), nullable=False)
    encrypted_payload: str = Column(Text, nullable=False)
    active: bool = Column(Boolean, nullable=False, default=True, index=True)
    created_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    deactivated_at: datetime | None = Column(DateTime(timezone=True), nullable=True)


class PushDelivery(Base):
    __tablename__ = "push_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "subscription_id",
            name="uq_push_deliveries_notification_subscription",
        ),
    )

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    notification_id: str = Column(
        String(36), ForeignKey("notifications.id"), nullable=False, index=True
    )
    subscription_id: str = Column(
        String(36), ForeignKey("push_subscriptions.id"), nullable=False, index=True
    )
    status: str = Column(String(32), nullable=False, default="pending", index=True)
    attempt_count: int = Column(Integer, nullable=False, default=0)
    next_attempt_at: datetime | None = Column(
        DateTime(timezone=True), nullable=True, index=True
    )
    delivered_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    last_status_code: int | None = Column(Integer, nullable=True)
    created_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
