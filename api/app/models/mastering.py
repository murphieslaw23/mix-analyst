"""Mastering database models."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from api.app.db.session import Base


class MasteringPreset(Base):
    __tablename__ = "mastering_presets"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    target_lufs: Mapped[float] = mapped_column(Float, default=-14.0)
    true_peak_ceiling: Mapped[float] = mapped_column(Float, default=-1.0)
    target_lra: Mapped[float] = mapped_column(Float, default=7.0)
    eq_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    compressor_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MasteringJob(Base):
    __tablename__ = "mastering_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    media_id: Mapped[str] = mapped_column(String, ForeignKey("mixes.id"), index=True)
    preset_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("mastering_presets.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, default="pending")
    input_lufs: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_true_peak: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_lra: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_lufs: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_true_peak: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_lra: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
