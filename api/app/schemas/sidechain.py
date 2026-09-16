from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class SidechainProcessRequest(BaseModel):
    media_id: str
    threshold_db: Optional[float] = -12.0
    max_ducking_db: Optional[float] = 6.0
    auto_phase_align: bool = True

class SidechainProcessResponse(BaseModel):
    job_id: str
    media_id: str
    status: str
    phase_inverted: bool
    phase_correlation: float
    max_gain_reduction_db: float
    processed_bass_rms: float
    low_end_clarity_score: float

class SidechainReportResponse(BaseModel):
    job_id: str
    media_id: str
    status: str
    threshold_db: Optional[float] = None
    max_ducking_db: Optional[float] = None
    phase_inverted: Optional[bool] = None
    phase_correlation: Optional[float] = None
    max_gain_reduction_db: Optional[float] = None
    processed_bass_rms: Optional[float] = None
    low_end_clarity_score: Optional[float] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
