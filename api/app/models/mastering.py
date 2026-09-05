"""Mastering database models."""
from sqlalchemy import CheckConstraint, Column, String, Float, Integer, ForeignKey, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from api.app.db.session import Base

class MasteringPreset(Base):
    __tablename__ = "mastering_presets"
    __table_args__ = (
        CheckConstraint(
            "is_builtin IS TRUE OR is_legacy_shared IS TRUE OR project_id IS NOT NULL",
            name="ck_mastering_presets_owner_or_global",
        ),
    )

    id = Column(String, primary_key=True, index=True)
    # Built-ins are global; user-created presets are owned by one project and
    # must never be reusable merely by guessing their identifier.
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)
    # Pre-scope custom rows which cannot be attributed to one project remain
    # explicitly shared legacy profiles. This preserves their former global
    # behavior without pretending that a creator/tenant relationship existed.
    is_legacy_shared = Column(Boolean, nullable=False, default=False, server_default="0")
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    target_lufs = Column(Float, default=-14.0)
    true_peak_ceiling = Column(Float, default=-1.0)
    target_lra = Column(Float, default=7.0)
    eq_settings = Column(JSON, default=dict)
    compressor_settings = Column(JSON, default=dict)
    is_builtin = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MasteringJob(Base):
    __tablename__ = "mastering_jobs"

    id = Column(String, primary_key=True, index=True)
    media_id = Column(String, ForeignKey("media_assets.id"), nullable=False, index=True)
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
