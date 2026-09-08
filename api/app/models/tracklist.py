import uuid
from datetime import datetime, timezone

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


class TrackSegment(Base):
    __tablename__ = "track_segments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mix_id = Column(String(36), ForeignKey("mixes.id"), nullable=False, index=True)
    segment_index = Column(Integer, nullable=False)
    start_time_seconds = Column(Float, nullable=False)
    end_time_seconds = Column(Float, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    fingerprint = Column(Text, nullable=True)
    confidence = Column(Float, default=0.0, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    mix = relationship("Mix", back_populates="track_segments")
    match = relationship(
        "TrackMatch",
        back_populates="segment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TrackMatch(Base):
    __tablename__ = "track_matches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    segment_id = Column(
        String(36),
        ForeignKey("track_segments.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    mix_id = Column(String(36), ForeignKey("mixes.id"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    artist = Column(String(255), nullable=False)
    album = Column(String(255), nullable=True)
    label = Column(String(255), nullable=True)
    isrc = Column(String(50), nullable=True)
    acoustid_id = Column(String(100), nullable=True)
    musicbrainz_recording_id = Column(String(100), nullable=True)
    match_score = Column(Float, nullable=False)
    source = Column(String(50), default="acoustid", nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    segment = relationship("TrackSegment", back_populates="match")
