"""Stem separation and bassline analysis models."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from api.app.db.session import Base


class StemJob(Base):
    __tablename__ = "stem_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    media_id: Mapped[str] = mapped_column(String, ForeignKey("mixes.id"), index=True)
    model_name: Mapped[str] = mapped_column(String, default="htdemucs")
    status: Mapped[str] = mapped_column(String, default="pending")
    drums_path: Mapped[str | None] = mapped_column(String, nullable=True)
    bass_path: Mapped[str | None] = mapped_column(String, nullable=True)
    other_path: Mapped[str | None] = mapped_column(String, nullable=True)
    vocals_path: Mapped[str | None] = mapped_column(String, nullable=True)
    bass_fundamental_hz: Mapped[float | None] = mapped_column(Float, nullable=True)
    kick_sub_collision_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    resonance_peaks: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
