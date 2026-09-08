"""Broadcast and AzuraCast synchronization schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class BroadcastSyncRequest(BaseModel):
    station_id: str | None = "syco23_live"
    playlist_name: str | None = "Underground Freetekno Sets"
    scheduled_start: datetime | None = None
    inject_cue_markers: bool = True


class BroadcastSyncResponse(BaseModel):
    sync_id: str
    media_id: str
    station_id: str
    status: str
    playlist_name: str
    cue_markers_synced: int
    scheduled_start: datetime | None = None
    created_at: datetime
    synced_at: datetime | None = None


class AzuraCastWebhookPayload(BaseModel):
    event: str
    station: dict[str, Any]
    now_playing: dict[str, Any]
    listeners: dict[str, Any] | None = None
