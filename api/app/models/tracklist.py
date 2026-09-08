from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .media import Mix


class TrackSegment(Base):
    __tablename__ = "track_segments"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mix_id: str = Column(String(36), ForeignKey("mixes.id"), nullable=False, index=True)
    segment_index: int = Column(Integer, nullable=False)
    start_time_seconds: float = Column(Float, nullable=False)
    end_time_seconds: float = Column(Float, nullable=False)
    duration_seconds: float = Column(Float, nullable=False)
    fingerprint: str | None = Column(Text, nullable=True)
    confidence: float = Column(Float, default=0.0, nullable=False)

    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    mix: Mix = relationship("Mix", back_populates="track_segments")
    match: TrackMatch | None = relationship(
        "TrackMatch",
        back_populates="segment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TrackMatch(Base):
    __tablename__ = "track_matches"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    segment_id: str = Column(
        String(36),
        ForeignKey("track_segments.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    mix_id: str = Column(String(36), ForeignKey("mixes.id"), nullable=False, index=True)

    title: str = Column(String(255), nullable=False)
    artist: str = Column(String(255), nullable=False)
    album: str | None = Column(String(255), nullable=True)
    label: str | None = Column(String(255), nullable=True)
    isrc: str | None = Column(String(50), nullable=True)
    acoustid_id: str | None = Column(String(100), nullable=True)
    musicbrainz_recording_id: str | None = Column(String(100), nullable=True)
    match_score: float = Column(Float, nullable=False)
    source: str = Column(String(50), default="acoustid", nullable=False)

    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    segment: TrackSegment = relationship("TrackSegment", back_populates="match")
