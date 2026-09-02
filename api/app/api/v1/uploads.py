"""Authenticated, bounded resumable upload endpoints."""

from __future__ import annotations

from tempfile import TemporaryFile

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from ...config import settings
from ...db.session import get_db
from ...models.media import UploadSession
from ...schemas.auth import CurrentPrincipal
from ...schemas.upload import (
    UploadChunkResponse,
    UploadCompleteRequest,
    UploadCompleteResponse,
    UploadInitRequest,
    UploadInitResponse,
    UploadStatusResponse,
)
from ...services.storage import StorageService
from ...services.upload_sessions import (
    UploadExpiredError,
    UploadLifecycleError,
    UploadNotFoundError,
    UploadOffsetConflictError,
    UploadStateError,
    UploadTooLargeError,
    UploadValidationError,
    append_chunk,
    cleanup_expired_uploads,
    create_upload_session,
    finalize_upload,
)
from ..deps import get_current_principal, require_owned_upload_session


router = APIRouter()
storage = StorageService(settings.storage_root)


def _http_error(exc: UploadLifecycleError) -> HTTPException:
    if isinstance(exc, UploadNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, UploadOffsetConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, UploadExpiredError):
        return HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))
    if isinstance(exc, UploadTooLargeError):
        return HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc))
    if isinstance(exc, UploadValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, UploadStateError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload storage error")


async def _bounded_request_body(request: Request, max_bytes: int):
    """Stage a raw request body to a temporary file without unbounded reads."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                raise UploadTooLargeError(f"Chunk exceeds maximum size of {max_bytes} bytes")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Content-Length") from exc

    temporary = TemporaryFile(mode="w+b")
    received = 0
    try:
        async for payload in request.stream():
            received += len(payload)
            if received > max_bytes:
                raise UploadTooLargeError(f"Chunk exceeds maximum size of {max_bytes} bytes")
            temporary.write(payload)
        temporary.seek(0)
        return temporary
    except Exception:
        temporary.close()
        raise


@router.post("", response_model=UploadInitResponse, status_code=status.HTTP_201_CREATED)
def init_upload(
    req: UploadInitRequest,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    try:
        cleanup_expired_uploads(db, storage)
        return create_upload_session(
            db,
            principal,
            req.filename,
            req.total_size_bytes,
            req.content_type,
            storage,
            max_upload_size_bytes=settings.max_upload_size_bytes,
            max_chunk_size_bytes=settings.max_chunk_size_bytes,
            ttl_seconds=settings.upload_session_ttl_seconds,
        )
    except UploadLifecycleError as exc:
        raise _http_error(exc) from exc


@router.patch("/{upload_id}", response_model=UploadChunkResponse)
async def upload_chunk(
    upload_id: str,
    request: Request,
    upload_offset: str | None = Header(default=None, alias="Upload-Offset"),
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Append a raw upload body using the server's locked offset as authority."""
    # Preserve opaque project-scoped 404 behavior before rejecting a malformed
    # request or consuming its body. The lifecycle service repeats this query
    # under a row lock for the state-changing operation.
    require_owned_upload_session(db, principal, upload_id)
    db.rollback()
    if upload_offset is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload-Offset header is required")
    try:
        offset = int(upload_offset)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload-Offset must be an integer") from exc
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload-Offset must be non-negative")

    try:
        body = await _bounded_request_body(request, settings.max_chunk_size_bytes)
        try:
            next_offset = append_chunk(
                db,
                principal,
                upload_id,
                offset,
                body,
                storage,
                max_chunk_size_bytes=settings.max_chunk_size_bytes,
            )
        finally:
            body.close()
    except UploadLifecycleError as exc:
        raise _http_error(exc) from exc

    upload = db.get(UploadSession, upload_id)
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found")
    progress = round((next_offset / upload.total_size_bytes) * 100, 2)
    return UploadChunkResponse(
        upload_id=upload_id,
        bytes_received=next_offset,
        offset=next_offset,
        total_size_bytes=upload.total_size_bytes,
        progress_percent=min(progress, 100.0),
        status=upload.status.value,
    )


@router.post("/{upload_id}/complete", response_model=UploadCompleteResponse)
def complete_upload(
    upload_id: str,
    req: UploadCompleteRequest,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    try:
        finalized = finalize_upload(db, principal, upload_id, storage, title=req.title, artist=req.artist)
    except UploadLifecycleError as exc:
        raise _http_error(exc) from exc
    media = finalized.media_asset
    mix = finalized.mix
    return UploadCompleteResponse(
        mix_id=mix.id,
        media_asset_id=media.id,
        title=mix.title,
        artist=mix.artist,
        duration_seconds=media.duration_seconds,
        sample_rate=media.sample_rate,
        channels=media.channels,
        codec=media.codec,
        sha256_hash=media.sha256_hash,
        status=mix.status,
    )


@router.get("/{upload_id}", response_model=UploadStatusResponse)
def get_upload_status(
    upload_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    upload_session: UploadSession = require_owned_upload_session(db, principal, upload_id)
    progress = 0.0
    if upload_session.total_size_bytes > 0:
        progress = round((upload_session.offset / upload_session.total_size_bytes) * 100, 2)
    return UploadStatusResponse(
        upload_id=upload_session.id,
        filename=upload_session.filename,
        total_size_bytes=upload_session.total_size_bytes,
        bytes_received=upload_session.bytes_received,
        offset=upload_session.offset,
        progress_percent=min(progress, 100.0),
        status=upload_session.status.value,
        expires_at=upload_session.expires_at,
        created_at=upload_session.created_at,
        updated_at=upload_session.updated_at,
    )
