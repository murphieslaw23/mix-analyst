from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Json


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
    # Stored as JSON text columns (raw strings from the ORM) but passed
    # pre-parsed by some endpoints: accept either form, always emit objects.
    bpm_candidates: list[BpmCandidate] | Json[list[BpmCandidate]] = []
    detected_key: str
    camelot_code: str
    key_confidence: float
    integrated_lufs: float
    loudness_range_lra: float
    true_peak_db: float
    spectral_summary: dict[str, Any] | Json[dict[str, Any]] = {}
    quality_findings: list[QualityFinding] | Json[list[QualityFinding]] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
