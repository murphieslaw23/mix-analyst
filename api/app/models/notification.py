"""Durable, principal-scoped in-app notifications."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .job import Job


class Notification(Base):
    """A server-authoritative notification, never a Redis-only wake-up."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_notifications_dedupe_key"),
    )

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: str = Column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    user_id: str = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    job_id: str | None = Column(
        String(36), ForeignKey("jobs.id"), nullable=True, index=True
    )
    kind: str = Column(String(64), nullable=False)
    dedupe_key: str = Column(String(255), nullable=False)
    title: str = Column(String(255), nullable=False)
    body: str | None = Column(String(1024), nullable=True)
    deep_link: str = Column(String(255), nullable=False)
    read_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    dismissed_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    job: Job | None = relationship("Job", back_populates="notifications")
