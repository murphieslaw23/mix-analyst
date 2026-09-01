"""Broadcast and AzuraCast synchronization schemas."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime

class BroadcastSyncRequest(BaseModel):
    station_id: Optional[str] = "syco23_live"
    playlist_name: Optional[str] = "Underground Freetekno Sets"
    scheduled_start: Optional[datetime] = None
    inject_cue_markers: bool = True

class BroadcastSyncResponse(BaseModel):
    sync_id: str
    media_id: str
    station_id: str
    status: str
    playlist_name: str
    cue_markers_synced: int
    scheduled_start: Optional[datetime] = None
    created_at: datetime
    synced_at: Optional[datetime] = None

class AzuraCastWebhookPayload(BaseModel):
    event: str
    station: Dict[str, Any]
    now_playing: Dict[str, Any]
    listeners: Optional[Dict[str, Any]] = None
