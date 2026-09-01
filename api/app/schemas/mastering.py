"""Mastering Pydantic schemas."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime

class MasteringPresetResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    target_lufs: float
    true_peak_ceiling: float
    target_lra: float
    eq_settings: Dict[str, Any]
    compressor_settings: Dict[str, Any]
    is_builtin: bool

    class Config:
        from_attributes = True

class MasteringTriggerRequest(BaseModel):
    preset_id: Optional[str] = "sound_system_heavy"
    target_lufs: Optional[float] = None
    true_peak_ceiling: Optional[float] = None

class MasteringReportResponse(BaseModel):
    job_id: str
    media_id: str
    status: str
    preset_name: Optional[str] = None
    input_measurements: Dict[str, Any]
    output_measurements: Dict[str, Any]
    gain_adjust_db: float
    compliance_passed: bool
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
