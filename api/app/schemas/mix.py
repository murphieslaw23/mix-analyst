from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from .analysis import AnalysisResultOut
from .artifact import ArtifactOut


class MediaAssetOut(BaseModel):
    id: str
    original_filename: str
    file_size_bytes: int
    sha256_hash: str
    duration_seconds: float
    sample_rate: int
    channels: int
    codec: str
    bit_rate: Optional[int] = None
    format_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MixOut(BaseModel):
    id: str
    title: str
    artist: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    media_asset: MediaAssetOut
    analysis_result: Optional[AnalysisResultOut] = None
    artifacts: List[ArtifactOut] = []
    suggested_download_name: Optional[str] = None

    class Config:
        from_attributes = True


class MixListResponse(BaseModel):
    items: List[MixOut]
    total: int


class MixUpdateRequest(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
