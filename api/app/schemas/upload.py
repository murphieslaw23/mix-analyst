from datetime import datetime

from pydantic import BaseModel, Field


class UploadInitRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    total_size_bytes: int = Field(..., gt=0)
    content_type: str = Field(
        default="application/octet-stream", min_length=1, max_length=100
    )
    # Clients may suggest a chunk size, but the server caps every append.
    chunk_size: int | None = Field(default=None, gt=0)


class UploadSessionOut(BaseModel):
    upload_id: str
    upload_url: str
    filename: str
    total_size_bytes: int
    chunk_size: int
    offset: int
    expires_at: datetime
    status: str


class UploadInitResponse(UploadSessionOut):
    pass


class UploadChunkResponse(BaseModel):
    upload_id: str
    bytes_received: int
    offset: int
    total_size_bytes: int
    progress_percent: float
    status: str


class UploadCompleteRequest(BaseModel):
    title: str | None = None
    artist: str | None = None


class UploadCompleteResponse(BaseModel):
    mix_id: str
    media_asset_id: str
    title: str
    artist: str | None = None
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
    offset: int
    progress_percent: float
    status: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
