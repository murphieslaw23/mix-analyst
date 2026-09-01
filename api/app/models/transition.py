import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship

from ..db.session import Base


class TransitionEvent(Base):
    __tablename__ = "transition_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mix_id = Column(String(36), ForeignKey("mixes.id"), nullable=False, index=True)
    transition_index = Column(Integer, nullable=False)

    start_time_seconds = Column(Float, nullable=False)
    end_time_seconds = Column(Float, nullable=False)
    cue_in_time = Column(Float, nullable=False)
    cue_out_time = Column(Float, nullable=False)

    transition_type = Column(String(50), default="SMOOTH_BLEND", nullable=False)
    energy_delta = Column(Float, default=0.0, nullable=False)
    tempo_shift_bpm = Column(Float, default=0.0, nullable=False)
    camelot_compatibility = Column(String(50), default="PERFECT_MATCH", nullable=False)
    confidence = Column(Float, default=0.8, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    mix = relationship("Mix", back_populates="transitions")
