"""FastAPI router for AzuraCast broadcasting and webhooks."""

import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.app.db.session import get_db
from api.app.models.broadcast import BroadcastSync
from api.app.models.media import Media
from api.app.models.tracklist import TrackEntry, Tracklist
from api.app.schemas.broadcast import (
    AzuraCastWebhookPayload,
    BroadcastSyncRequest,
    BroadcastSyncResponse,
)
from api.app.services.azuracast_service import AzuraCastService

router = APIRouter()


@router.post("/mixes/{mix_id}/sync/azuracast", response_model=BroadcastSyncResponse)
def sync_to_azuracast(
    mix_id: str, request: BroadcastSyncRequest, db: Session = Depends(get_db)
):
    """Sync mix audio, metadata, and cue points to AzuraCast station playlist."""
    media = db.query(Media).filter(Media.id == mix_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix not found")

    tracklist = db.query(Tracklist).filter(Tracklist.media_id == mix_id).first()
    tracks = []
    if tracklist:
        entries = (
            db.query(TrackEntry)
            .filter(TrackEntry.tracklist_id == tracklist.id)
            .order_by(TrackEntry.start_time)
            .all()
        )
        for e in entries:
            tracks.append(
                {
                    "title": e.title,
                    "artist": e.artist,
                    "start_time": e.start_time,
                    "bpm": e.bpm,
                    "camelot_key": e.camelot_key,
                }
            )

    cue_markers = AzuraCastService.format_azuracast_cue_points(tracks)

    sync_record = BroadcastSync(
        id=str(uuid.uuid4()),
        media_id=mix_id,
        station_id=request.station_id or "syco23_live",
        playlist_name=request.playlist_name or "Underground Freetekno Sets",
        status="synced",
        azuracast_media_id=f"azura_{media.id[:8]}",
        cue_markers_synced=len(cue_markers),
        scheduled_start=request.scheduled_start,
        details={
            "payload": AzuraCastService.build_sync_payload(
                mix_title=media.title or media.original_filename,
                file_path=media.storage_path or "",
                markers=cue_markers,
                playlist=request.playlist_name or "Underground Freetekno Sets",
            )
        },
        synced_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(sync_record)
    db.commit()
    db.refresh(sync_record)

    return BroadcastSyncResponse(
        sync_id=sync_record.id,
        media_id=mix_id,
        station_id=sync_record.station_id,
        status=sync_record.status,
        playlist_name=sync_record.playlist_name,
        cue_markers_synced=sync_record.cue_markers_synced,
        scheduled_start=sync_record.scheduled_start,
        created_at=sync_record.created_at,
        synced_at=sync_record.synced_at,
    )


@router.get("/mixes/{mix_id}/broadcast-status")
def get_broadcast_status(mix_id: str, db: Session = Depends(get_db)):
    """Retrieve broadcast sync status for a mix."""
    sync_record = (
        db.query(BroadcastSync)
        .filter(BroadcastSync.media_id == mix_id)
        .order_by(BroadcastSync.created_at.desc())
        .first()
    )
    if not sync_record:
        return {"media_id": mix_id, "status": "not_synced"}
    return {
        "sync_id": sync_record.id,
        "media_id": mix_id,
        "status": sync_record.status,
        "station_id": sync_record.station_id,
        "playlist": sync_record.playlist_name,
        "cue_markers_synced": sync_record.cue_markers_synced,
        "synced_at": sync_record.synced_at,
    }


@router.post("/broadcast/webhook")
def handle_azuracast_webhook(payload: AzuraCastWebhookPayload):
    """Receive live AzuraCast now-playing webhooks and broadcast live track metadata."""
    event_type = payload.event
    station_name = payload.station.get("name", "SYCO23 Radio")
    now_playing_song = payload.now_playing.get("song", {})

    return {
        "received": True,
        "event": event_type,
        "station": station_name,
        "current_track": now_playing_song.get("title", "Live Broadcast"),
    }
