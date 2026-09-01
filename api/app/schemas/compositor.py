from pydantic import BaseModel
from typing import Optional, List

class BroadcastStreamRequest(BaseModel):
    media_id: str
    stream_title: Optional[str] = "SYSTEM CORRUPT Broadcast"
    artist_name: Optional[str] = "SYCO23 Sound System"
    bpm: Optional[float] = 152.0
    camelot_key: Optional[str] = "9A"
    destinations: Optional[List[str]] = ["local_preview"]

class BroadcastStreamResponse(BaseModel):
    job_id: str
    media_id: str
    status: str
    preview_url: Optional[str]
    filter_complex: str
    command_args: List[str]
