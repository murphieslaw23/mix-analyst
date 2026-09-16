from datetime import datetime

from pydantic import BaseModel


class SidechainProcessRequest(BaseModel):
    media_id: str
    threshold_db: float | None = -12.0
    max_ducking_db: float | None = 6.0
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
    threshold_db: float | None = None
    max_ducking_db: float | None = None
    phase_inverted: bool | None = None
    phase_correlation: float | None = None
    max_gain_reduction_db: float | None = None
    processed_bass_rms: float | None = None
    low_end_clarity_score: float | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
