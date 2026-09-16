"""Sidechain processing job records."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from api.app.db.session import Base


class SidechainJob(Base):
    __tablename__ = "sidechain_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    media_id: Mapped[str] = mapped_column(String, ForeignKey("mixes.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="queued")
    threshold_db: Mapped[float] = mapped_column(Float, default=-12.0)
    max_ducking_db: Mapped[float] = mapped_column(Float, default=6.0)
    phase_inverted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    phase_correlation: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_gain_reduction_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    processed_bass_rms: Mapped[float | None] = mapped_column(Float, nullable=True)
    low_end_clarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
