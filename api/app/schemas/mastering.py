"""Mastering Pydantic schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MasteringPresetResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    target_lufs: float
    true_peak_ceiling: float
    target_lra: float
    eq_settings: dict[str, Any]
    compressor_settings: dict[str, Any]
    is_builtin: bool

    class Config:
        from_attributes = True


class MasteringTriggerRequest(BaseModel):
    preset_id: str | None = "sound_system_heavy"
    target_lufs: float | None = None
    true_peak_ceiling: float | None = None


class MasteringReportResponse(BaseModel):
    job_id: str
    media_id: str
    status: str
    preset_name: str | None = None
    input_measurements: dict[str, Any]
    output_measurements: dict[str, Any]
    gain_adjust_db: float
    compliance_passed: bool
    created_at: datetime | None = None
    completed_at: datetime | None = None
