from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
    bit_rate: int | None = None
    format_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MixOut(BaseModel):
    id: str
    title: str
    artist: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    media_asset: MediaAssetOut
    analysis_result: AnalysisResultOut | None = None

    model_config = ConfigDict(from_attributes=True)


class MixListResponse(BaseModel):
    items: list[MixOut]
    total: int


class MixUpdateRequest(BaseModel):
    title: str | None = None
    artist: str | None = None


class MixTrackOut(BaseModel):
    """Track cue in the shape the PWA waveform/timeline consumes."""

    id: str | None = None
    title: str
    artist: str
    start_time: float
    end_time: float | None = None
    bpm: float | None = None
    camelot_key: str | None = None


class MixTransitionOut(BaseModel):
    """Transition zone in the shape the PWA timeline consumes."""

    id: str | None = None
    start_time: float
    end_time: float | None = None
    transition_type: str | None = None
    from_key: str | None = None
    to_key: str | None = None
    harmonic_compatibility: str | None = None


class MixDetailOut(BaseModel):
    """Full mix payload for the PWA: metadata, audio URL, cues, transitions."""

    id: str
    title: str
    artist: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    original_filename: str
    duration_seconds: float
    bpm: float | None = None
    camelot_key: str | None = None
    audio_url: str
    tracks: list[MixTrackOut] = []
    transitions: list[MixTransitionOut] = []


class PeaksResponse(BaseModel):
    """Downsampled waveform peaks for the PWA timeline (values 0..1)."""

    mix_id: str
    buckets: int
    duration_seconds: float
    peaks: list[float]
