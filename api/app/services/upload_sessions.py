"""Transactional, project-owned upload session lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.media import MediaAsset, Mix, UploadSession, UploadStatus
from ..schemas.auth import CurrentPrincipal
from ..schemas.upload import UploadSessionOut
from .audio_probe import AudioProbeError, AudioProbeResult, probe_audio
from .storage import ChunkTooLargeError, StorageService, derived_object_key


class UploadLifecycleError(Exception):
    pass


class UploadNotFoundError(UploadLifecycleError):
    pass


class UploadOffsetConflictError(UploadLifecycleError):
    pass


class UploadExpiredError(UploadLifecycleError):
    pass


class UploadStateError(UploadLifecycleError):
    pass


class UploadTooLargeError(UploadLifecycleError):
    pass


class UploadValidationError(UploadLifecycleError):
    pass


@dataclass(frozen=True)
class FinalizedUpload:
    media_asset: MediaAsset
    mix: Mix


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(upload: UploadSession, now: datetime | None = None) -> bool:
    expires_at = upload.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= (now or _now())


def _quarantine_key(project_id: str, session_id: str) -> str:
    # Both values are server-issued identity values, and are deliberately not
    # influenced by filename or other client input.
    return f"projects/{project_id}/quarantine/upload/v1/{session_id}"


def _session_out(upload: UploadSession) -> UploadSessionOut:
    return UploadSessionOut(
        upload_id=upload.id,
        upload_url=f"/api/v1/{upload.id}",
        filename=upload.filename,
        total_size_bytes=upload.total_size_bytes,
        chunk_size=upload.chunk_size,
        offset=upload.offset,
        expires_at=upload.expires_at,
        status=upload.status.value,
    )


def create_upload_session(
    db: Session,
    principal: CurrentPrincipal,
    filename: str,
    byte_length: int,
    content_type: str,
    storage: StorageService,
    *,
    max_upload_size_bytes: int,
    max_chunk_size_bytes: int,
    ttl_seconds: int,
) -> UploadSessionOut:
    """Create a bounded, expiring server-owned quarantine object and row."""
    if byte_length > max_upload_size_bytes:
        raise UploadTooLargeError(f"File exceeds maximum allowed size of {max_upload_size_bytes} bytes")
    session_id = str(uuid.uuid4())
    quarantine_key = _quarantine_key(principal.project_id, session_id)
    upload = UploadSession(
        id=session_id,
        project_id=principal.project_id,
        filename=filename,
        total_size_bytes=byte_length,
        bytes_received=0,
        offset=0,
        chunk_size=min(max_chunk_size_bytes, byte_length),
        content_type=content_type,
        quarantine_key=quarantine_key,
        # No absolute path is written for a new session. The legacy column is
        # retained only so existing database rows can be migrated safely.
        temp_path=quarantine_key,
        expires_at=_now() + timedelta(seconds=ttl_seconds),
        status=UploadStatus.PENDING,
    )
    storage.create_quarantine_object(quarantine_key)
    try:
        with db.begin():
            db.add(upload)
    except Exception:
        storage.delete_object(quarantine_key)
        raise
    return _session_out(upload)


def _locked_owned_upload(db: Session, principal: CurrentPrincipal, session_id: str) -> UploadSession:
    upload = db.scalar(
        select(UploadSession)
        .where(UploadSession.id == session_id, UploadSession.project_id == principal.project_id)
        .with_for_update()
    )
    if upload is None:
        raise UploadNotFoundError("Upload session not found")
    if not upload.quarantine_key:
        # A legacy raw-path row must not become a path-capability through this
        # endpoint. Its caller sees the same opaque 404 as an absent session.
        raise UploadNotFoundError("Upload session not found")
    return upload


def _assert_appendable(upload: UploadSession) -> None:
    if upload.status not in {UploadStatus.PENDING, UploadStatus.UPLOADING}:
        raise UploadStateError(f"Cannot append to {upload.status.value} upload session")


def append_chunk(
    db: Session,
    principal: CurrentPrincipal,
    session_id: str,
    offset: int,
    chunk: BinaryIO,
    storage: StorageService,
    *,
    max_chunk_size_bytes: int,
) -> int:
    """Append under a row lock using the database offset as the authority."""
    cleanup_key: str | None = None
    next_offset: int | None = None
    with db.begin():
        upload = _locked_owned_upload(db, principal, session_id)
        if _is_expired(upload):
            upload.status = UploadStatus.ABORTED
            cleanup_key = upload.quarantine_key
        else:
            _assert_appendable(upload)
            if offset != upload.offset:
                raise UploadOffsetConflictError(
                    f"Offset mismatch: expected offset {upload.offset}, got {offset}"
                )
            if storage.object_size(upload.quarantine_key) != upload.offset:
                raise UploadLifecycleError("Quarantine object does not match its authoritative offset")
            remaining = upload.total_size_bytes - upload.offset
            if remaining <= 0:
                raise UploadStateError("Upload already contains its declared byte length")
            try:
                written = storage.write_limited_chunk(
                    upload.quarantine_key, chunk, min(max_chunk_size_bytes, remaining)
                )
            except ChunkTooLargeError as exc:
                raise UploadTooLargeError(str(exc)) from exc
            except ValueError as exc:
                raise UploadValidationError(str(exc)) from exc
            next_offset = upload.offset + written
            upload.offset = next_offset
            upload.bytes_received = next_offset
            upload.status = UploadStatus.UPLOADING
    if cleanup_key is not None:
        storage.delete_object(cleanup_key)
        raise UploadExpiredError("Upload session has expired")
    assert next_offset is not None
    return next_offset


def _mark_failed(db: Session, principal: CurrentPrincipal, session_id: str) -> str | None:
    with db.begin():
        upload = _locked_owned_upload(db, principal, session_id)
        upload.status = UploadStatus.FAILED
        return upload.quarantine_key


def finalize_upload(
    db: Session,
    principal: CurrentPrincipal,
    session_id: str,
    storage: StorageService,
    *,
    title: str | None = None,
    artist: str | None = None,
) -> FinalizedUpload:
    """Validate a complete quarantine object and promote it after DB commit."""
    cleanup_key: str | None = None
    with db.begin():
        upload = _locked_owned_upload(db, principal, session_id)
        if _is_expired(upload):
            upload.status = UploadStatus.ABORTED
            cleanup_key = upload.quarantine_key
        else:
            _assert_appendable(upload)
            if upload.offset != upload.total_size_bytes:
                raise UploadValidationError(
                    f"Incomplete upload: expected {upload.total_size_bytes} bytes, got {upload.offset} bytes"
                )
            if storage.object_size(upload.quarantine_key) != upload.offset:
                raise UploadLifecycleError("Quarantine object does not match its authoritative offset")
            quarantine_key = upload.quarantine_key
    if cleanup_key is not None:
        storage.delete_object(cleanup_key)
        raise UploadExpiredError("Upload session has expired")

    try:
        probe_result: AudioProbeResult = probe_audio(storage.object_path(quarantine_key))
        sha256_hash = storage.compute_sha256(quarantine_key)
    except (AudioProbeError, OSError, ValueError) as exc:
        failed_key = _mark_failed(db, principal, session_id)
        if failed_key:
            storage.delete_object(failed_key)
        raise UploadValidationError(f"Invalid audio format: {exc}") from exc

    final_key = derived_object_key(principal.project_id, sha256_hash, "source", "v1")
    with db.begin():
        upload = _locked_owned_upload(db, principal, session_id)
        _assert_appendable(upload)
        if upload.offset != upload.total_size_bytes or storage.object_size(upload.quarantine_key) != upload.offset:
            raise UploadLifecycleError("Upload changed during finalization")
        existing_asset = db.scalar(select(MediaAsset).where(MediaAsset.storage_path == final_key))
        is_deduplicated = existing_asset is not None
        if existing_asset is None:
            try:
                # A second same-project finalization can select before the
                # first transaction commits. Keep its unique-key collision to
                # a savepoint so the outer transaction can reuse the winner.
                with db.begin_nested():
                    media_asset = MediaAsset(
                        project_id=principal.project_id,
                        original_filename=upload.filename,
                        storage_path=final_key,
                        file_size_bytes=upload.total_size_bytes,
                        sha256_hash=sha256_hash,
                        mime_type=upload.content_type,
                        duration_seconds=probe_result.duration_seconds,
                        sample_rate=probe_result.sample_rate,
                        channels=probe_result.channels,
                        codec=probe_result.codec,
                        bit_rate=probe_result.bit_rate,
                        format_name=probe_result.format_name,
                    )
                    db.add(media_asset)
                    db.flush()
            except IntegrityError:
                media_asset = db.scalar(select(MediaAsset).where(MediaAsset.storage_path == final_key))
                if media_asset is None:
                    raise UploadLifecycleError("Final asset conflict could not be resolved") from None
                is_deduplicated = True
        else:
            media_asset = existing_asset
        mix = Mix(
            project_id=principal.project_id,
            title=title.strip() if title and title.strip() else Path(upload.filename).stem,
            artist=artist.strip() if artist and artist.strip() else None,
            media_asset_id=media_asset.id,
            status="ready",
        )
        db.add(mix)
        db.flush()
        upload.sha256_hash = sha256_hash
        upload.status = UploadStatus.COMPLETED
        quarantine_key = upload.quarantine_key
        media_asset_id = media_asset.id
        mix_id = mix.id

    try:
        if is_deduplicated:
            storage.delete_object(quarantine_key)
        else:
            storage.promote(quarantine_key, final_key)
    except OSError as exc:
        with db.begin():
            upload = _locked_owned_upload(db, principal, session_id)
            upload.status = UploadStatus.FAILED
            failed_mix = db.get(Mix, mix_id)
            if failed_mix is not None:
                db.delete(failed_mix)
            if not is_deduplicated:
                failed_asset = db.get(MediaAsset, media_asset_id)
                if failed_asset is not None:
                    db.delete(failed_asset)
        raise UploadLifecycleError("Could not promote validated upload") from exc

    # Rehydrate from the committed rows; callers never need a filesystem path.
    return FinalizedUpload(media_asset=db.get(MediaAsset, media_asset_id), mix=db.get(Mix, mix_id))


def cleanup_expired_uploads(
    db: Session,
    storage: StorageService,
    project_id: str,
    now: datetime | None = None,
) -> int:
    """Abort this project's expired sessions and remove their quarantine objects."""
    cutoff = now or _now()
    expired_ids = db.scalars(
        select(UploadSession.id).where(
            UploadSession.project_id == project_id,
            UploadSession.status.in_((UploadStatus.PENDING, UploadStatus.UPLOADING)),
            UploadSession.expires_at <= cutoff,
        )
    ).all()
    db.rollback()
    cleanup_keys: list[str] = []
    for session_id in expired_ids:
        with db.begin():
            upload = db.scalar(
                select(UploadSession)
                .where(UploadSession.id == session_id, UploadSession.project_id == project_id)
                .with_for_update()
            )
            if upload is not None and upload.status in {UploadStatus.PENDING, UploadStatus.UPLOADING} and _is_expired(upload, cutoff):
                upload.status = UploadStatus.ABORTED
                if upload.quarantine_key:
                    cleanup_keys.append(upload.quarantine_key)
    for key in cleanup_keys:
        storage.delete_object(key)
    return len(cleanup_keys)
