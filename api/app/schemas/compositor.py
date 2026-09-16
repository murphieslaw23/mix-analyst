from pydantic import BaseModel


class BroadcastStreamRequest(BaseModel):
    media_id: str
    stream_title: str | None = "SYSTEM CORRUPT Broadcast"
    artist_name: str | None = "SYCO23 Sound System"
    bpm: float | None = 152.0
    camelot_key: str | None = "9A"
    destinations: list[str] | None = ["local_preview"]


class BroadcastStreamResponse(BaseModel):
    job_id: str
    media_id: str
    status: str
    preview_url: str | None
    filter_complex: str
    command_args: list[str]
