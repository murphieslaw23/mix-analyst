from datetime import datetime
from typing import Any

from pydantic import BaseModel


class BpmCandidate(BaseModel):
    bpm: float
    confidence: float
    support_count: int


class QualityFinding(BaseModel):
    type: str
    severity: str
    description: str
    timestamp_range: list[float] | None = None


class AnalysisResultOut(BaseModel):
    id: str
    mix_id: str
    media_asset_id: str
    primary_bpm: float
    bpm_confidence: float
    bpm_candidates: list[BpmCandidate] = []
    detected_key: str
    camelot_code: str
    key_confidence: float
    integrated_lufs: float
    loudness_range_lra: float
    true_peak_db: float
    spectral_summary: dict[str, Any] = {}
    quality_findings: list[QualityFinding] = []
    created_at: datetime

    class Config:
        from_attributes = True
