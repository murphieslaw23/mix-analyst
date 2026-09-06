import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from ..db.session import Base


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

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    mix_id = Column(String(36), ForeignKey("mixes.id"), nullable=False, index=True)
    batch_id = Column(String(36), ForeignKey("batches.id"), nullable=True, index=True)
    job_type = Column(SQLEnum(JobType), default=JobType.ANALYSIS, nullable=False)
    status = Column(SQLEnum(JobStatus), default=JobStatus.QUEUED, nullable=False, index=True)
    progress_percent = Column(Float, default=0.0, nullable=False)
    current_stage = Column(String(100), nullable=True)
    parameters = Column(JSON, default=dict, nullable=False)
    celery_task_id = Column(String(100), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    event_sequence = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    stage_runs = relationship("StageRun", back_populates="job", cascade="all, delete-orphan", order_by="StageRun.started_at")
    attempts = relationship("JobAttempt", back_populates="job", cascade="all, delete-orphan", order_by="JobAttempt.attempt_number")
    outbox_messages = relationship("OutboxMessage", back_populates="job", cascade="all, delete-orphan")
    events = relationship("JobEvent", back_populates="job", cascade="all, delete-orphan", order_by="JobEvent.sequence")
    notifications = relationship("Notification", back_populates="job", cascade="all, delete-orphan")
    batch = relationship("Batch", back_populates="jobs")


class JobAttempt(Base):
    __tablename__ = "job_attempts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    attempt_number = Column(Integer, default=1, nullable=False)
    status = Column(SQLEnum(JobStatus), default=JobStatus.RUNNING, nullable=False)
    worker_hostname = Column(String(255), nullable=True)
    # A worker lease is a fencing token, not merely a host name.  A redelivered
    # task may reclaim an abandoned attempt after its lease expires, while an
    # old process can no longer complete or heartbeat the replacement claim.
    claim_token = Column(String(64), nullable=True, index=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    error_details = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("Job", back_populates="attempts")


class StageRun(Base):
    __tablename__ = "stage_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    stage_name = Column(String(100), nullable=False)
    stage_version = Column(String(50), default="1.0.0", nullable=False)
    param_hash = Column(String(64), nullable=True)
    status = Column(SQLEnum(StageStatus), default=StageStatus.PENDING, nullable=False)
    progress_percent = Column(Float, default=0.0, nullable=False)
    stage_output = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("Job", back_populates="stage_runs")
