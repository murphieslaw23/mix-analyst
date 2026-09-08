from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .batch import Batch
    from .job_event import JobEvent
    from .notification import Notification
    from .outbox import OutboxMessage


class JobType(str, enum.Enum):
    ANALYSIS = "ANALYSIS"
    FINGERPRINT = "FINGERPRINT"
    RESTORATION = "RESTORATION"
    MASTERING = "MASTERING"
    EXPORT = "EXPORT"


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StageStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Job(Base):
    __tablename__ = "jobs"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: str = Column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    mix_id: str = Column(String(36), ForeignKey("mixes.id"), nullable=False, index=True)
    batch_id: str | None = Column(
        String(36), ForeignKey("batches.id"), nullable=True, index=True
    )
    job_type: JobType = Column(
        SQLEnum(JobType), default=JobType.ANALYSIS, nullable=False
    )
    status: JobStatus = Column(
        SQLEnum(JobStatus), default=JobStatus.QUEUED, nullable=False, index=True
    )
    progress_percent: Mapped[float] = Column(Float, default=0.0, nullable=False)
    current_stage: str | None = Column(String(100), nullable=True)
    parameters: dict[str, Any] = Column(JSON, default=dict, nullable=False)
    celery_task_id: str | None = Column(String(100), nullable=True, index=True)
    error_message: str | None = Column(Text, nullable=True)
    event_sequence: int = Column(Integer, default=0, nullable=False)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    finished_at: datetime | None = Column(DateTime(timezone=True), nullable=True)

    stage_runs: Mapped[list[StageRun]] = relationship(
        "StageRun",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="StageRun.started_at",
    )
    attempts: Mapped[list[JobAttempt]] = relationship(
        "JobAttempt",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobAttempt.attempt_number",
    )
    outbox_messages: Mapped[list[OutboxMessage]] = relationship(
        "OutboxMessage", back_populates="job", cascade="all, delete-orphan"
    )
    events: Mapped[list[JobEvent]] = relationship(
        "JobEvent",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobEvent.sequence",
    )
    notifications: Mapped[list[Notification]] = relationship(
        "Notification", back_populates="job", cascade="all, delete-orphan"
    )
    batch: Mapped[Batch | None] = relationship("Batch", back_populates="jobs")


class JobAttempt(Base):
    __tablename__ = "job_attempts"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: str = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    attempt_number: int = Column(Integer, default=1, nullable=False)
    status: JobStatus = Column(
        SQLEnum(JobStatus), default=JobStatus.RUNNING, nullable=False
    )
    worker_hostname: str | None = Column(String(255), nullable=True)
    # A worker lease is a fencing token, not merely a host name. A redelivered
    # task may reclaim an abandoned attempt after its lease expires, while an
    # old process can no longer complete or heartbeat the replacement claim.
    claim_token: str | None = Column(String(64), nullable=True, index=True)
    last_heartbeat_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at: datetime | None = Column(
        DateTime(timezone=True), nullable=True, index=True
    )
    error_details: str | None = Column(Text, nullable=True)
    started_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    finished_at: datetime | None = Column(DateTime(timezone=True), nullable=True)

    job: Mapped[Job] = relationship("Job", back_populates="attempts")


class StageRun(Base):
    __tablename__ = "stage_runs"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: str = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    stage_name: str = Column(String(100), nullable=False)
    stage_version: str = Column(String(50), default="1.0.0", nullable=False)
    param_hash: str | None = Column(String(64), nullable=True)
    status: StageStatus = Column(
        SQLEnum(StageStatus), default=StageStatus.PENDING, nullable=False
    )
    progress_percent: Mapped[float] = Column(Float, default=0.0, nullable=False)
    stage_output: str | None = Column(Text, nullable=True)
    error_message: str | None = Column(Text, nullable=True)
    started_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    finished_at: datetime | None = Column(DateTime(timezone=True), nullable=True)

    job: Mapped[Job] = relationship("Job", back_populates="stage_runs")
