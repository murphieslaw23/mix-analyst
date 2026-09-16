from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.app.api.deps import require_api_key
from api.app.config import settings
from api.app.db.session import get_db
from api.app.models.job import JobType
from api.app.models.media import Mix
from api.app.schemas.compositor import BroadcastStreamRequest, BroadcastStreamResponse
from api.app.services.pipeline_jobs import enqueue_pipeline_job
from worker.broadcast.ffmpeg_compositor import FFmpegBroadcastCompositor

router = APIRouter()


@router.post(
    "/broadcast/render-stream", response_model=BroadcastStreamResponse, status_code=202
)
def render_broadcast_stream(
    request: BroadcastStreamRequest,
    db: Annotated[Session, Depends(get_db)],
    _auth: Annotated[None, Depends(require_api_key)],
):
    """Enqueue a real 16:9 1080p FFmpeg render; track via the job id (SSE).

    Returns the exact filter graph and command the worker will execute so
    operators can inspect them while the render runs. Completion is recorded
    as a BroadcastSync row, visible via GET /mixes/{id}/broadcast-status.
    """
    media = db.query(Mix).filter(Mix.id == request.media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    params: dict[str, Any] = {
        "stream_title": request.stream_title or "Live Set",
        "artist_name": request.artist_name or "SYSTEM CORRUPT",
        "bpm": request.bpm or 150.0,
        "camelot_key": request.camelot_key or "8A",
        "station_id": "syco23_live",
        "playlist_name": "Underground Freetekno Sets",
    }
    job = enqueue_pipeline_job(
        db,
        mix_id=request.media_id,
        job_type=JobType.BROADCAST_RENDER,
        task_name="tasks.run_broadcast_render",
        task_args=lambda job_id: [job_id, request.media_id, params],
        queue="exports",
    )

    input_audio = str(Path(settings.storage_root) / media.media_asset.storage_path)
    output_dest = str(
        Path(settings.storage_root)
        / "assets"
        / "derived"
        / "broadcast"
        / f"{request.media_id}_1080p.mp4"
    )

    filter_complex = FFmpegBroadcastCompositor.build_filter_complex(
        title=params["stream_title"],
        artist=params["artist_name"],
        bpm=params["bpm"],
        camelot_key=params["camelot_key"],
    )
    cmd = FFmpegBroadcastCompositor.build_ffmpeg_command(
        input_audio=input_audio,
        output_dest=output_dest,
        title=params["stream_title"],
        artist=params["artist_name"],
        bpm=params["bpm"],
        camelot_key=params["camelot_key"],
    )

    return BroadcastStreamResponse(
        job_id=job.id,
        media_id=request.media_id,
        status="rendering",
        preview_url=None,
        filter_complex=filter_complex,
        command_args=cmd,
    )
