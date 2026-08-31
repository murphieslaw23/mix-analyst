from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class UploadInitRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    total_size_bytes: int = Field(..., gt=0)
    chunk_size: int = Field(default=5 * 1024 * 1024, gt=0)


class UploadInitResponse(BaseModel):
    upload_id: str
    filename: str
    total_size_bytes: int
    chunk_size: int
    status: str


class UploadChunkResponse(BaseModel):
    upload_id: str
    bytes_received: int
    total_size_bytes: int
    progress_percent: float
    status: str


class UploadCompleteRequest(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None


class UploadCompleteResponse(BaseModel):
    mix_id: str
    media_asset_id: str
    title: str
    artist: Optional[str] = None
    duration_seconds: float
    sample_rate: int
    channels: int
    codec: str
    sha256_hash: str
    status: str


class UploadStatusResponse(BaseModel):
    upload_id: str
    filename: str
    total_size_bytes: int
    bytes_received: int
    progress_percent: float
    status: str
    created_at: datetime
    updated_at: datetime
