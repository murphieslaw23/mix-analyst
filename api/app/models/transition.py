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
)
from sqlalchemy.orm import relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .media import Mix


class TransitionEvent(Base):
    __tablename__ = "transition_events"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mix_id: str = Column(String(36), ForeignKey("mixes.id"), nullable=False, index=True)
    transition_index: int = Column(Integer, nullable=False)

    start_time_seconds: float = Column(Float, nullable=False)
    end_time_seconds: float = Column(Float, nullable=False)
    cue_in_time: float = Column(Float, nullable=False)
    cue_out_time: float = Column(Float, nullable=False)

    transition_type: str = Column(String(50), default="SMOOTH_BLEND", nullable=False)
    energy_delta: float = Column(Float, default=0.0, nullable=False)
    tempo_shift_bpm: float = Column(Float, default=0.0, nullable=False)
    camelot_compatibility: str = Column(
        String(50), default="PERFECT_MATCH", nullable=False
    )
    confidence: float = Column(Float, default=0.8, nullable=False)

    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    mix: Mix = relationship("Mix", back_populates="transitions")
