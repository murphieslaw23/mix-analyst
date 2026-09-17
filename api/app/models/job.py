import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .job_event import JobEvent
    from .outbox import OutboxMessage


class JobType(str, enum.Enum):
    ANALYSIS = "ANALYSIS"
    FINGERPRINT = "FINGERPRINT"
    RESTORATION = "RESTORATION"
    MASTERING = "MASTERING"
    STEM_SEPARATION = "STEM_SEPARATION"
    SIDECHAIN = "SIDECHAIN"
    BROADCAST_RENDER = "BROADCAST_RENDER"
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

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    mix_id: Mapped[str] = mapped_column(String(36), ForeignKey("mixes.id"), index=True)
    job_type: Mapped[JobType] = mapped_column(
        SQLEnum(JobType), default=JobType.ANALYSIS
    )
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus), default=JobStatus.QUEUED, index=True
    )
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    current_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    stage_runs: Mapped[list["StageRun"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="StageRun.started_at",
    )
    attempts: Mapped[list["JobAttempt"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobAttempt.attempt_number",
    )
    outbox_messages: Mapped[list["OutboxMessage"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["JobEvent"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobEvent.sequence",
    )


class JobAttempt(Base):
    __tablename__ = "job_attempts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus), default=JobStatus.RUNNING
    )
    worker_hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    job: Mapped["Job"] = relationship(back_populates="attempts")


class StageRun(Base):
    __tablename__ = "stage_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    stage_name: Mapped[str] = mapped_column(String(100))
    stage_version: Mapped[str] = mapped_column(String(50), default="1.0.0")
    param_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[StageStatus] = mapped_column(
        SQLEnum(StageStatus), default=StageStatus.PENDING
    )
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    stage_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    job: Mapped["Job"] = relationship(back_populates="stage_runs")
