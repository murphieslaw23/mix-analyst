"""Persistent parent records for bounded groups of mastering jobs."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .job import Job


class BatchStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PARTIAL_FAILED = "PARTIAL_FAILED"
    CANCELLED = "CANCELLED"


class Batch(Base):
    __tablename__ = "batches"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: str = Column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    preset: dict[str, Any] = Column(JSON, default=dict, nullable=False)
    max_parallelism: int = Column(Integer, nullable=False)
    # These are a persisted read model. They are never incremented directly:
    # services.batches recomputes every value from the child jobs table.
    status: BatchStatus = Column(
        SQLEnum(BatchStatus), default=BatchStatus.QUEUED, nullable=False, index=True
    )
    total_count: int = Column(Integer, default=0, nullable=False)
    completed_count: int = Column(Integer, default=0, nullable=False)
    failed_count: int = Column(Integer, default=0, nullable=False)
    cancelled_count: int = Column(Integer, default=0, nullable=False)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    jobs: list[Job] = relationship(
        "Job", back_populates="batch", order_by="Job.created_at"
    )

    @property
    def items(self) -> list[Job]:
        """API name for durable child jobs; no parallel in-memory item state."""
        return self.jobs
