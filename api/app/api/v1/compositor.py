import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.app.db.session import get_db
from api.app.models.media import Media
from api.app.schemas.compositor import BroadcastStreamRequest, BroadcastStreamResponse
from worker.broadcast.ffmpeg_compositor import FFmpegBroadcastCompositor

router = APIRouter()


@router.post("/broadcast/render-stream", response_model=BroadcastStreamResponse)
def render_broadcast_stream(
    request: BroadcastStreamRequest, db: Session = Depends(get_db)
):
    """Generate 16:9 1080p audio-reactive broadcast stream parameters."""
    media = db.query(Media).filter(Media.id == request.media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    filter_complex = FFmpegBroadcastCompositor.build_filter_complex(
        title=request.stream_title or "Live Set",
        artist=request.artist_name or "SYSTEM CORRUPT",
        bpm=request.bpm or 150.0,
        camelot_key=request.camelot_key or "8A",
    )

    cmd = FFmpegBroadcastCompositor.build_ffmpeg_command(
        input_audio=f"/storage/audio/{request.media_id}.wav",
        output_dest=f"/storage/broadcast/{request.media_id}_1080p.mp4",
        title=request.stream_title or "Live Set",
        artist=request.artist_name or "SYSTEM CORRUPT",
        bpm=request.bpm or 150.0,
        camelot_key=request.camelot_key or "8A",
    )

    return BroadcastStreamResponse(
        job_id=str(uuid.uuid4()),
        media_id=request.media_id,
        status="configured",
        preview_url=f"/storage/broadcast/{request.media_id}_1080p.mp4",
        filter_complex=filter_complex,
        command_args=cmd,
    )
