import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    kind: Mapped[str] = mapped_column(String(50))
    dedupe_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    deep_link: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="unread")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    endpoint_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "subscription_id",
            name="uq_notification_subscription",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    notification_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notifications.id"), index=True
    )
    subscription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("push_subscriptions.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
