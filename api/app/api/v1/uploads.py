from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header, status
from sqlalchemy.orm import Session
from pathlib import Path
import uuid

from ...db.session import get_db
from ...config import settings
from ...models.media import UploadSession, UploadStatus, MediaAsset, Mix
from ...services.storage import StorageService
from ...services.audio_probe import probe_audio, AudioProbeError
from ...schemas.upload import (
    UploadInitRequest,
    UploadInitResponse,
    UploadChunkResponse,
    UploadCompleteRequest,
    UploadCompleteResponse,
    UploadStatusResponse,
)

router = APIRouter()
storage = StorageService(settings.storage_root)


@router.post("", response_model=UploadInitResponse, status_code=status.HTTP_201_CREATED)
def init_upload(req: UploadInitRequest, db: Session = Depends(get_db)):
    """Initialize a new resumable upload session."""
    if req.total_size_bytes > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_size_bytes / (1024 * 1024 * 1024):.1f} GB",
        )

    session_id = str(uuid.uuid4())
    temp_file = storage.create_upload_session_file(session_id)

    upload_session = UploadSession(
        id=session_id,
        filename=req.filename,
        total_size_bytes=req.total_size_bytes,
        chunk_size=req.chunk_size,
        bytes_received=0,
        temp_path=str(temp_file),
        status=UploadStatus.PENDING,
    )
    db.add(upload_session)
    db.commit()
    db.refresh(upload_session)

    return UploadInitResponse(
        upload_id=upload_session.id,
        filename=upload_session.filename,
        total_size_bytes=upload_session.total_size_bytes,
        chunk_size=upload_session.chunk_size,
        status=upload_session.status.value,
    )


@router.patch("/{upload_id}", response_model=UploadChunkResponse)
async def upload_chunk(
    upload_id: str,
    file: UploadFile = File(...),
    offset: int = Form(...),
    db: Session = Depends(get_db),
):
    """Append a chunk to the active upload session."""
    upload_session = db.query(UploadSession).filter(UploadSession.id == upload_id).first()
    if not upload_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found")

    if upload_session.status in [UploadStatus.COMPLETED, UploadStatus.FAILED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot upload chunk for session with status {upload_session.status.value}",
        )

    temp_path = Path(upload_session.temp_path)
    chunk_bytes = await file.read()

    try:
        new_size = storage.append_chunk(temp_path, chunk_bytes, offset)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        upload_session.status = UploadStatus.FAILED
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Storage error: {e}")

    upload_session.bytes_received = new_size
    upload_session.status = UploadStatus.UPLOADING
    db.commit()
    db.refresh(upload_session)

    progress = round((new_size / upload_session.total_size_bytes) * 100, 2)

    return UploadChunkResponse(
        upload_id=upload_session.id,
        bytes_received=new_size,
        total_size_bytes=upload_session.total_size_bytes,
        progress_percent=min(progress, 100.0),
        status=upload_session.status.value,
    )


@router.post("/{upload_id}/complete", response_model=UploadCompleteResponse)
def complete_upload(
    upload_id: str,
    req: UploadCompleteRequest,
    db: Session = Depends(get_db),
):
    """Finalize the upload, probe audio validity with ffprobe, and create the MediaAsset and Mix."""
    upload_session = db.query(UploadSession).filter(UploadSession.id == upload_id).first()
    if not upload_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found")

    temp_path = Path(upload_session.temp_path)
    if not temp_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Temporary upload file not found")

    # Verify total size
    actual_size = temp_path.stat().st_size
    if actual_size != upload_session.total_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incomplete upload: expected {upload_session.total_size_bytes} bytes, got {actual_size} bytes",
        )

    # Validate audio with ffprobe
    try:
        probe_result = probe_audio(temp_path)
    except AudioProbeError as e:
        upload_session.status = UploadStatus.FAILED
        storage.delete_file(temp_path)
        db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid audio format: {e}")

    # Compute SHA-256
    sha256 = storage.compute_sha256(temp_path)
    upload_session.sha256_hash = sha256

    # Atomically move from quarantine to permanent audio storage
    asset_id = str(uuid.uuid4())
    rel_path, abs_path = storage.finalize_asset(temp_path, asset_id, upload_session.filename)

    # Persist MediaAsset
    media_asset = MediaAsset(
        id=asset_id,
        original_filename=upload_session.filename,
        storage_path=rel_path,
        file_size_bytes=actual_size,
        sha256_hash=sha256,
        duration_seconds=probe_result.duration_seconds,
        sample_rate=probe_result.sample_rate,
        channels=probe_result.channels,
        codec=probe_result.codec,
        bit_rate=probe_result.bit_rate,
        format_name=probe_result.format_name,
    )
    db.add(media_asset)

    # Derive mix title from request or original filename
    mix_title = req.title.strip() if req.title and req.title.strip() else Path(upload_session.filename).stem
    mix = Mix(
        title=mix_title,
        artist=req.artist.strip() if req.artist and req.artist.strip() else None,
        media_asset_id=media_asset.id,
        status="ready",
    )
    db.add(mix)

    upload_session.status = UploadStatus.COMPLETED
    db.commit()
    db.refresh(media_asset)
    db.refresh(mix)

    return UploadCompleteResponse(
        mix_id=mix.id,
        media_asset_id=media_asset.id,
        title=mix.title,
        artist=mix.artist,
        duration_seconds=media_asset.duration_seconds,
        sample_rate=media_asset.sample_rate,
        channels=media_asset.channels,
        codec=media_asset.codec,
        sha256_hash=media_asset.sha256_hash,
        status=mix.status,
    )


@router.get("/{upload_id}", response_model=UploadStatusResponse)
def get_upload_status(upload_id: str, db: Session = Depends(get_db)):
    """Get status of an active or completed upload session."""
    upload_session = db.query(UploadSession).filter(UploadSession.id == upload_id).first()
    if not upload_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found")

    progress = 0.0
    if upload_session.total_size_bytes > 0:
        progress = round((upload_session.bytes_received / upload_session.total_size_bytes) * 100, 2)

    return UploadStatusResponse(
        upload_id=upload_session.id,
        filename=upload_session.filename,
        total_size_bytes=upload_session.total_size_bytes,
        bytes_received=upload_session.bytes_received,
        progress_percent=min(progress, 100.0),
        status=upload_session.status.value,
        created_at=upload_session.created_at,
        updated_at=upload_session.updated_at,
    )
