from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .analysis import AnalysisResult
    from .artifact import Artifact
    from .tracklist import TrackSegment
    from .transition import TransitionEvent


class UploadStatus(str, enum.Enum):
    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: str = Column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    original_filename: str = Column(String(255), nullable=False)
    storage_path: str = Column(String(512), nullable=False, unique=True)
    file_size_bytes: int = Column(BigInteger, nullable=False)
    sha256_hash: str = Column(String(64), nullable=False, index=True)
    mime_type: str | None = Column(String(100), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sample_rate: int = Column(BigInteger, nullable=False)
    channels: int = Column(BigInteger, nullable=False)
    codec: str = Column(String(50), nullable=False)
    bit_rate: int | None = Column(BigInteger, nullable=True)
    format_name: str | None = Column(String(50), nullable=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    mixes: Mapped[list[Mix]] = relationship(
        "Mix", back_populates="media_asset", cascade="all, delete-orphan"
    )


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: str = Column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    filename: str = Column(String(255), nullable=False)
    total_size_bytes: int = Column(BigInteger, nullable=False)
    bytes_received: int = Column(BigInteger, default=0, nullable=False)
    # ``offset`` is the authoritative append position. ``bytes_received`` is
    # retained for the existing response contract and is always updated with it.
    offset: int = Column(BigInteger, default=0, nullable=False)
    chunk_size: int = Column(BigInteger, default=5 * 1024 * 1024, nullable=False)
    sha256_hash: str | None = Column(String(64), nullable=True)
    content_type: str = Column(
        String(100), default="application/octet-stream", nullable=False
    )
    quarantine_key: str = Column(String(512), default="", nullable=False)
    # Upload completion is a recoverable two-phase operation. Rows remain
    # non-complete until their validated quarantine object is durably present
    # at ``final_key``; a retry can then finish promotion without exposing a
    # mix that points at missing bytes.
    promotion_state: str = Column(String(32), default="NONE", nullable=False)
    final_key: str | None = Column(String(512), nullable=True)
    media_asset_id: str | None = Column(
        String(36), ForeignKey("media_assets.id"), nullable=True
    )
    mix_id: str | None = Column(String(36), ForeignKey("mixes.id"), nullable=True)
    expires_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    # Kept only to allow the migration to leave old rows inspectable. New
    # uploads never persist or consume an absolute filesystem path.
    temp_path: str = Column(String(512), nullable=False)
    status: UploadStatus = Column(
        SQLEnum(UploadStatus), default=UploadStatus.PENDING, nullable=False
    )
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


class Mix(Base):
    __tablename__ = "mixes"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: str = Column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    title: str = Column(String(255), nullable=False)
    artist: str | None = Column(String(255), nullable=True)
    media_asset_id: str = Column(
        String(36), ForeignKey("media_assets.id"), nullable=False
    )
    status: str = Column(String(50), default="ready", nullable=False)
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

    media_asset: Mapped[MediaAsset] = relationship("MediaAsset", back_populates="mixes")
    analysis_result: Mapped[AnalysisResult | None] = relationship(
        "AnalysisResult",
        back_populates="mix",
        cascade="all, delete-orphan",
    )
    track_segments: Mapped[list[TrackSegment]] = relationship(
        "TrackSegment", back_populates="mix", cascade="all, delete-orphan"
    )
    transitions: Mapped[list[TransitionEvent]] = relationship(
        "TransitionEvent", back_populates="mix", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list[Artifact]] = relationship(
        "Artifact", back_populates="mix", cascade="all, delete-orphan"
    )
