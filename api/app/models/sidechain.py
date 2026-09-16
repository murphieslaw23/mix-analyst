"""Sidechain processing job records."""
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from api.app.db.session import Base


class SidechainJob(Base):
    __tablename__ = "sidechain_jobs"

    id = Column(String, primary_key=True, index=True)
    media_id = Column(String, ForeignKey("mixes.id"), nullable=False, index=True)
    status = Column(String, default="queued")  # queued, processing, completed, failed
    threshold_db = Column(Float, default=-12.0)
    max_ducking_db = Column(Float, default=6.0)
    phase_inverted = Column(Boolean, nullable=True)
    phase_correlation = Column(Float, nullable=True)
    max_gain_reduction_db = Column(Float, nullable=True)
    processed_bass_rms = Column(Float, nullable=True)
    low_end_clarity_score = Column(Float, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
