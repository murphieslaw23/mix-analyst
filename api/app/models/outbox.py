from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .job import Job


class OutboxMessage(Base):
    """A committed command that has not necessarily reached the broker yet."""

    __tablename__ = "outbox_messages"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: str = Column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    aggregate_id: str = Column(
        String(36), ForeignKey("jobs.id"), nullable=False, index=True
    )
    kind: str = Column(String(100), nullable=False, index=True)
    payload: dict[str, Any] = Column(JSON, nullable=False)
    delivery_attempts: int = Column(Integer, default=0, nullable=False)
    last_error: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    delivered_at: datetime | None = Column(DateTime(timezone=True), nullable=True, index=True)

    job: Job = relationship("Job", back_populates="outbox_messages")
