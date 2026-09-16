from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
from pathlib import Path
from api.app.db.session import get_db
from api.app.config import settings
from api.app.models.media import Mix
from api.app.schemas.compositor import BroadcastStreamRequest, BroadcastStreamResponse
from worker.broadcast.ffmpeg_compositor import FFmpegBroadcastCompositor

router = APIRouter()

@router.post("/broadcast/render-stream", response_model=BroadcastStreamResponse)
def render_broadcast_stream(request: BroadcastStreamRequest, db: Session = Depends(get_db)):
    """Preview 16:9 1080p audio-reactive broadcast filter graph (no render yet).

    This endpoint validates the mix, builds the real FFmpeg filter_complex
    and command for inspection, but does NOT render video — no render worker
    exists yet, so there is no output file and nothing is persisted.
    """
    media = db.query(Mix).filter(Mix.id == request.media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    input_audio = str(Path(settings.storage_root) / media.media_asset.storage_path)
    output_dest = str(
        Path(settings.storage_root) / "assets" / "derived" / f"{request.media_id}_1080p.mp4"
    )

    filter_complex = FFmpegBroadcastCompositor.build_filter_complex(
        title=request.stream_title or "Live Set",
        artist=request.artist_name or "SYSTEM CORRUPT",
        bpm=request.bpm or 150.0,
        camelot_key=request.camelot_key or "8A"
    )

    cmd = FFmpegBroadcastCompositor.build_ffmpeg_command(
        input_audio=input_audio,
        output_dest=output_dest,
        title=request.stream_title or "Live Set",
        artist=request.artist_name or "SYSTEM CORRUPT",
        bpm=request.bpm or 150.0,
        camelot_key=request.camelot_key or "8A"
    )

    return BroadcastStreamResponse(
        job_id=str(uuid.uuid4()),
        media_id=request.media_id,
        status="filter_preview",
        preview_url=None,
        filter_complex=filter_complex,
        command_args=cmd
    )
