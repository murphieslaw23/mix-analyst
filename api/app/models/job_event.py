"""Durable, ordered events emitted by a job within its owning project."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .job import Job


class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_job_events_job_id_sequence"),
    )

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: str = Column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    job_id: str = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    attempt_number: int = Column(Integer, nullable=False, default=1)
    sequence: int = Column(Integer, nullable=False)
    event_type: str = Column(String(100), nullable=False)
    payload: dict[str, Any] = Column(JSON, nullable=False)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    job: Mapped[Job] = relationship("Job", back_populates="events")
