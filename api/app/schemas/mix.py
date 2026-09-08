from datetime import datetime

from pydantic import BaseModel

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
    bit_rate: int | None = None
    format_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class MixOut(BaseModel):
    id: str
    title: str
    artist: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    media_asset: MediaAssetOut
    analysis_result: AnalysisResultOut | None = None
    artifacts: list[ArtifactOut] = []
    suggested_download_name: str | None = None

    class Config:
        from_attributes = True


class MixListResponse(BaseModel):
    items: list[MixOut]
    total: int


class MixUpdateRequest(BaseModel):
    title: str | None = None
    artist: str | None = None
