from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class TrackMatchOut(BaseModel):
    id: str
    segment_id: str
    mix_id: str
    title: str
    artist: str
    album: Optional[str] = None
    label: Optional[str] = None
    isrc: Optional[str] = None
    acoustid_id: Optional[str] = None
    musicbrainz_recording_id: Optional[str] = None
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
    fingerprint: Optional[str] = None
    confidence: float
    match: Optional[TrackMatchOut] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TracklistResponse(BaseModel):
    mix_id: str
    total_tracks: int
    identified_tracks: int
    tracks: List[TrackSegmentOut]
