"""Mastering database models."""
from sqlalchemy import Column, String, Float, Integer, ForeignKey, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from api.app.db.session import Base

class MasteringPreset(Base):
    __tablename__ = "mastering_presets"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    target_lufs = Column(Float, default=-14.0)
    true_peak_ceiling = Column(Float, default=-1.0)
    target_lra = Column(Float, default=7.0)
    eq_settings = Column(JSON, default=dict)
    compressor_settings = Column(JSON, default=dict)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MasteringJob(Base):
    __tablename__ = "mastering_jobs"

    id = Column(String, primary_key=True, index=True)
    media_id = Column(String, ForeignKey("media.id"), nullable=False, index=True)
    preset_id = Column(String, ForeignKey("mastering_presets.id"), nullable=True)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    input_lufs = Column(Float, nullable=True)
    input_true_peak = Column(Float, nullable=True)
    input_lra = Column(Float, nullable=True)
    output_lufs = Column(Float, nullable=True)
    output_true_peak = Column(Float, nullable=True)
    output_lra = Column(Float, nullable=True)
    output_storage_path = Column(String, nullable=True)
    metrics = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
