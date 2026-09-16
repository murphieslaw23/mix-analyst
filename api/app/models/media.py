import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .analysis import AnalysisResult
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

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(512), unique=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(nullable=False)
    sample_rate: Mapped[int] = mapped_column(BigInteger)
    channels: Mapped[int] = mapped_column(BigInteger)
    codec: Mapped[str] = mapped_column(String(50))
    bit_rate: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    format_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    mixes: Mapped[list["Mix"]] = relationship(
        back_populates="media_asset", cascade="all, delete-orphan"
    )


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    filename: Mapped[str] = mapped_column(String(255))
    total_size_bytes: Mapped[int] = mapped_column(BigInteger)
    bytes_received: Mapped[int] = mapped_column(BigInteger, default=0)
    chunk_size: Mapped[int] = mapped_column(BigInteger, default=5 * 1024 * 1024)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    temp_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[UploadStatus] = mapped_column(
        SQLEnum(UploadStatus), default=UploadStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Mix(Base):
    __tablename__ = "mixes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255))
    artist: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id")
    )
    status: Mapped[str] = mapped_column(String(50), default="ready")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    media_asset: Mapped["MediaAsset"] = relationship(back_populates="mixes")
    analysis_result: Mapped["AnalysisResult | None"] = relationship(
        back_populates="mix", uselist=False, cascade="all, delete-orphan"
    )
    track_segments: Mapped[list["TrackSegment"]] = relationship(
        back_populates="mix", cascade="all, delete-orphan"
    )
    transitions: Mapped[list["TransitionEvent"]] = relationship(
        back_populates="mix", cascade="all, delete-orphan"
    )
