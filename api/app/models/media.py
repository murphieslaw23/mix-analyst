import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Float,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from ..db.session import Base


class UploadStatus(str, enum.Enum):
    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False, unique=True)
    file_size_bytes = Column(BigInteger, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    mime_type = Column(String(100), nullable=True)
    duration_seconds = Column(Float, nullable=False)
    sample_rate = Column(BigInteger, nullable=False)
    channels = Column(BigInteger, nullable=False)
    codec = Column(String(50), nullable=False)
    bit_rate = Column(BigInteger, nullable=True)
    format_name = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    mixes = relationship("Mix", back_populates="media_asset", cascade="all, delete-orphan")


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    total_size_bytes = Column(BigInteger, nullable=False)
    bytes_received = Column(BigInteger, default=0, nullable=False)
    chunk_size = Column(BigInteger, default=5 * 1024 * 1024, nullable=False)
    sha256_hash = Column(String(64), nullable=True)
    temp_path = Column(String(512), nullable=False)
    status = Column(SQLEnum(UploadStatus), default=UploadStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Mix(Base):
    __tablename__ = "mixes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    artist = Column(String(255), nullable=True)
    media_asset_id = Column(String(36), ForeignKey("media_assets.id"), nullable=False)
    status = Column(String(50), default="ready", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    media_asset = relationship("MediaAsset", back_populates="mixes")
    analysis_result = relationship("AnalysisResult", back_populates="mix", uselist=False, cascade="all, delete-orphan")
    track_segments = relationship("TrackSegment", back_populates="mix", cascade="all, delete-orphan")
    transitions = relationship("TransitionEvent", back_populates="mix", cascade="all, delete-orphan")
