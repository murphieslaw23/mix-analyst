"""Persistent parent records for bounded groups of mastering jobs."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from ..db.session import Base


class BatchStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PARTIAL_FAILED = "PARTIAL_FAILED"
    CANCELLED = "CANCELLED"


class Batch(Base):
    __tablename__ = "batches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    preset = Column(JSON, default=dict, nullable=False)
    max_parallelism = Column(Integer, nullable=False)
    # These are a persisted read model. They are never incremented directly:
    # services.batches recomputes every value from the child jobs table.
    status = Column(SQLEnum(BatchStatus), default=BatchStatus.QUEUED, nullable=False, index=True)
    total_count = Column(Integer, default=0, nullable=False)
    completed_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    cancelled_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    jobs = relationship("Job", back_populates="batch", order_by="Job.created_at")

    @property
    def items(self):
        """API name for durable child jobs; no parallel in-memory item state."""
        return self.jobs
