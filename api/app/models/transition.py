import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .media import Mix


class TransitionEvent(Base):
    __tablename__ = "transition_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    mix_id: Mapped[str] = mapped_column(String(36), ForeignKey("mixes.id"), index=True)
    transition_index: Mapped[int] = mapped_column(Integer)

    start_time_seconds: Mapped[float] = mapped_column(Float)
    end_time_seconds: Mapped[float] = mapped_column(Float)
    cue_in_time: Mapped[float] = mapped_column(Float)
    cue_out_time: Mapped[float] = mapped_column(Float)

    transition_type: Mapped[str] = mapped_column(String(50), default="SMOOTH_BLEND")
    energy_delta: Mapped[float] = mapped_column(Float, default=0.0)
    tempo_shift_bpm: Mapped[float] = mapped_column(Float, default=0.0)
    camelot_compatibility: Mapped[str] = mapped_column(
        String(50), default="PERFECT_MATCH"
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.8)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    mix: Mapped["Mix"] = relationship(back_populates="transitions")
