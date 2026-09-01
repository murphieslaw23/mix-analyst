"""Pydantic schemas for stem separation and bassline analysis."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime

class StemSeparationRequest(BaseModel):
    model_name: Optional[str] = "htdemucs"
    analyze_bassline: bool = True

class StemSeparationResponse(BaseModel):
    job_id: str
    media_id: str
    status: str
    model_name: str
    stems: Dict[str, Optional[str]]
    bassline_analysis: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime] = None
