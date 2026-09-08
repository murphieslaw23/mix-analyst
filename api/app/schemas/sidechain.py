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
