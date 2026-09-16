from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from .analysis import AnalysisResultOut


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

    class Config:
        from_attributes = True


class MixListResponse(BaseModel):
    items: List[MixOut]
    total: int


class MixUpdateRequest(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None


class MixTrackOut(BaseModel):
    """Track cue in the shape the PWA waveform/timeline consumes."""

    id: Optional[str] = None
    title: str
    artist: str
    start_time: float
    end_time: Optional[float] = None
    bpm: Optional[float] = None
    camelot_key: Optional[str] = None


class MixTransitionOut(BaseModel):
    """Transition zone in the shape the PWA timeline consumes."""

    id: Optional[str] = None
    start_time: float
    end_time: Optional[float] = None
    transition_type: Optional[str] = None
    from_key: Optional[str] = None
    to_key: Optional[str] = None
    harmonic_compatibility: Optional[str] = None


class MixDetailOut(BaseModel):
    """Full mix payload for the PWA: metadata, audio URL, cues, transitions."""

    id: str
    title: str
    artist: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    original_filename: str
    duration_seconds: float
    bpm: Optional[float] = None
    camelot_key: Optional[str] = None
    audio_url: str
    tracks: List[MixTrackOut] = []
    transitions: List[MixTransitionOut] = []
