"""Pydantic schemas for stem separation and bassline analysis."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class StemSeparationRequest(BaseModel):
    model_name: str | None = "htdemucs"
    analyze_bassline: bool = True


class StemSeparationResponse(BaseModel):
    job_id: str
    media_id: str
    status: str
    model_name: str
    stems: dict[str, str | None]
    bassline_analysis: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None
