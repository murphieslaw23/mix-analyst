import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .media import Mix


class TrackSegment(Base):
    __tablename__ = "track_segments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    mix_id: Mapped[str] = mapped_column(String(36), ForeignKey("mixes.id"), index=True)
    segment_index: Mapped[int] = mapped_column(Integer)
    start_time_seconds: Mapped[float] = mapped_column(Float)
    end_time_seconds: Mapped[float] = mapped_column(Float)
    duration_seconds: Mapped[float] = mapped_column(Float)
    fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    mix: Mapped["Mix"] = relationship(back_populates="track_segments")
    match: Mapped["TrackMatch | None"] = relationship(
        back_populates="segment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TrackMatch(Base):
    __tablename__ = "track_matches"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    segment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("track_segments.id"),
        unique=True,
        index=True,
    )
    mix_id: Mapped[str] = mapped_column(String(36), ForeignKey("mixes.id"), index=True)

    title: Mapped[str] = mapped_column(String(255))
    artist: Mapped[str] = mapped_column(String(255))
    album: Mapped[str | None] = mapped_column(String(255), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    isrc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    acoustid_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    musicbrainz_recording_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    match_score: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(50), default="acoustid")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    segment: Mapped["TrackSegment"] = relationship(back_populates="match")
