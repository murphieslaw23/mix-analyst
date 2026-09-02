"""Stem separation and bassline analysis models."""
from sqlalchemy import Column, String, Float, Integer, ForeignKey, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from api.app.db.session import Base

class StemJob(Base):
    __tablename__ = "stem_jobs"

    id = Column(String, primary_key=True, index=True)
    media_id = Column(String, ForeignKey("media_assets.id"), nullable=False, index=True)
    model_name = Column(String, default="htdemucs")
    status = Column(String, default="pending")  # pending, processing, completed, failed
    drums_path = Column(String, nullable=True)
    bass_path = Column(String, nullable=True)
    other_path = Column(String, nullable=True)
    vocals_path = Column(String, nullable=True)
    bass_fundamental_hz = Column(Float, nullable=True)
    kick_sub_collision_score = Column(Float, nullable=True)
    resonance_peaks = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
