from datetime import datetime

from pydantic import BaseModel


class TrackMatchOut(BaseModel):
    id: str
    segment_id: str
    mix_id: str
    title: str
    artist: str
    album: str | None = None
    label: str | None = None
    isrc: str | None = None
    acoustid_id: str | None = None
    musicbrainz_recording_id: str | None = None
    match_score: float
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class TrackSegmentOut(BaseModel):
    id: str
    mix_id: str
    segment_index: int
    start_time_seconds: float
    end_time_seconds: float
    duration_seconds: float
    fingerprint: str | None = None
    confidence: float
    match: TrackMatchOut | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class TracklistResponse(BaseModel):
    mix_id: str
    total_tracks: int
    identified_tracks: int
    tracks: list[TrackSegmentOut]
