"""Transactional, project-owned upload session lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO

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
        raise UploadTooLargeError(
            f"File exceeds maximum allowed size of {max_upload_size_bytes} bytes"
        )
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


def _locked_owned_upload(
    db: Session, principal: CurrentPrincipal, session_id: str
) -> UploadSession:
    upload = db.scalar(
        select(UploadSession)
        .where(
            UploadSession.id == session_id,
            UploadSession.project_id == principal.project_id,
        )
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
            object_size = storage.object_size(upload.quarantine_key)
            if object_size < upload.offset:
                raise UploadLifecycleError(
                    "Quarantine object is missing committed upload bytes"
                )
            if object_size > upload.offset:
                # Recover the fsync-before-commit crash window.  The database
                # offset is authoritative, so discard the uncommitted tail and
                # append the caller's retry at the requested offset.
                storage.truncate_object(upload.quarantine_key, upload.offset)
            remaining = upload.total_size_bytes - upload.offset
            if remaining <= 0:
                raise UploadStateError(
                    "Upload already contains its declared byte length"
                )
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


def _mark_failed(
    db: Session, principal: CurrentPrincipal, session_id: str
) -> str | None:
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
    """Validate then complete a recoverable, two-phase object promotion.

    The initial database transaction creates a non-visible ``finalizing`` mix
    and marks the upload ``PENDING``.  Only a later transaction marks it
    complete after the immutable object is present.  A crash in between is
    safely resumed by another completion request instead of exposing a mix
    whose storage key does not exist.
    """
    # This service owns its transaction boundaries. Callers may have performed
    # a read (which starts SQLAlchemy's implicit transaction) while checking a
    # pending promotion, so release that read scope before the locked sequence.
    db.rollback()
    probe_result: AudioProbeResult | None = None
    quarantine_key: str | None = None
    cleanup_key: str | None = None
    pending_media_asset_id: str | None = None
    pending_mix_id: str | None = None
    final_key: str | None = None

    with db.begin():
        upload = _locked_owned_upload(db, principal, session_id)
        if (
            upload.promotion_state == "PROMOTED"
            and upload.media_asset_id
            and upload.mix_id
        ):
            promoted_asset = db.get(MediaAsset, upload.media_asset_id)
            promoted_mix = db.get(Mix, upload.mix_id)
            if (
                promoted_asset is None
                or promoted_mix is None
                or promoted_asset.project_id != principal.project_id
                or promoted_mix.project_id != principal.project_id
            ):
                raise UploadLifecycleError(
                    "Promoted upload references are unavailable"
                )
            return FinalizedUpload(media_asset=promoted_asset, mix=promoted_mix)
        if (
            upload.promotion_state == "PENDING"
            and upload.final_key
            and upload.media_asset_id
            and upload.mix_id
        ):
            # A prior caller already validated bytes and committed durable
            # references; do not reprobe or create a duplicate mix.
            quarantine_key = upload.quarantine_key
            final_key = upload.final_key
            pending_media_asset_id = upload.media_asset_id
            pending_mix_id = upload.mix_id
        elif _is_expired(upload):
            upload.status = UploadStatus.ABORTED
            cleanup_key = upload.quarantine_key
        else:
            _assert_appendable(upload)
            if upload.offset != upload.total_size_bytes:
                raise UploadValidationError(
                    f"Incomplete upload: expected {upload.total_size_bytes} bytes, got {upload.offset} bytes"
                )
            if storage.object_size(upload.quarantine_key) != upload.offset:
                raise UploadLifecycleError(
                    "Quarantine object does not match its authoritative offset"
                )
            quarantine_key = upload.quarantine_key
    if cleanup_key is not None:
        storage.delete_object(cleanup_key)
        raise UploadExpiredError("Upload session has expired")

    if final_key is None:
        assert quarantine_key is not None
        try:
            probe_result = probe_audio(storage.object_path(quarantine_key))
            sha256_hash = storage.compute_sha256(quarantine_key)
        except (AudioProbeError, OSError, ValueError) as exc:
            failed_key = _mark_failed(db, principal, session_id)
            if failed_key:
                storage.delete_object(failed_key)
            # Probe diagnostics can include absolute paths and ffprobe stderr.
            raise UploadValidationError("Uploaded file is not valid audio") from exc

        final_key = derived_object_key(
            principal.project_id, sha256_hash, "source", "v1"
        )
        with db.begin():
            upload = _locked_owned_upload(db, principal, session_id)
            _assert_appendable(upload)
            if (
                upload.offset != upload.total_size_bytes
                or storage.object_size(upload.quarantine_key) != upload.offset
            ):
                raise UploadLifecycleError("Upload changed during finalization")
            existing_asset = db.scalar(
                select(MediaAsset).where(MediaAsset.storage_path == final_key)
            )
            if existing_asset is None:
                try:
                    # A same-project concurrent finalization may win after our
                    # initial lookup.  Reuse the durable unique-key winner.
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
                    winner = db.scalar(
                        select(MediaAsset).where(MediaAsset.storage_path == final_key)
                    )
                    if winner is None:
                        raise UploadLifecycleError(
                            "Final asset conflict could not be resolved"
                        ) from None
                    media_asset = winner
            else:
                media_asset = existing_asset
            mix = Mix(
                project_id=principal.project_id,
                title=title.strip()
                if title and title.strip()
                else Path(upload.filename).stem,
                artist=artist.strip() if artist and artist.strip() else None,
                media_asset_id=media_asset.id,
                status="finalizing",
            )
            db.add(mix)
            db.flush()
            upload.sha256_hash = sha256_hash
            upload.final_key = final_key
            upload.media_asset_id = media_asset.id
            upload.mix_id = mix.id
            upload.promotion_state = "PENDING"
            pending_media_asset_id = media_asset.id
            pending_mix_id = mix.id

    assert quarantine_key is not None and final_key is not None
    assert pending_media_asset_id is not None and pending_mix_id is not None
    try:
        if storage.object_exists(final_key):
            # A deduplicated winner already owns the object; this session only
            # needs to discard its quarantine copy.
            storage.delete_object(quarantine_key)
        else:
            storage.promote(quarantine_key, final_key)
    except OSError as exc:
        # Keep PENDING state and finalizing references intact for a retry or
        # trusted reconciliation task.  Nothing points to the absent object as
        # a ready result.
        raise UploadLifecycleError("Could not promote validated upload") from exc

    with db.begin():
        upload = _locked_owned_upload(db, principal, session_id)
        if upload.promotion_state != "PENDING" or upload.final_key != final_key:
            raise UploadLifecycleError("Upload promotion state changed unexpectedly")
        if not storage.object_exists(final_key):
            raise UploadLifecycleError("Promoted upload object is unavailable")
        promoted_mix = db.get(Mix, pending_mix_id)
        promoted_asset = db.get(MediaAsset, pending_media_asset_id)
        if (
            promoted_mix is None
            or promoted_asset is None
            or promoted_mix.project_id != principal.project_id
            or promoted_asset.project_id != principal.project_id
        ):
            raise UploadLifecycleError("Upload promotion references are unavailable")
        promoted_mix.status = "ready"
        upload.status = UploadStatus.COMPLETED
        upload.promotion_state = "PROMOTED"

    return FinalizedUpload(media_asset=promoted_asset, mix=promoted_mix)


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
            UploadSession.promotion_state != "PENDING",
            UploadSession.expires_at <= cutoff,
        )
    ).all()
    db.rollback()
    cleanup_keys: list[str] = []
    for session_id in expired_ids:
        with db.begin():
            upload = db.scalar(
                select(UploadSession)
                .where(
                    UploadSession.id == session_id,
                    UploadSession.project_id == project_id,
                )
                .with_for_update()
            )
            if (
                upload is not None
                and upload.promotion_state != "PENDING"
                and upload.status in {UploadStatus.PENDING, UploadStatus.UPLOADING}
                and _is_expired(upload, cutoff)
            ):
                upload.status = UploadStatus.ABORTED
                if upload.quarantine_key:
                    cleanup_keys.append(upload.quarantine_key)
    for key in cleanup_keys:
        storage.delete_object(key)
    return len(cleanup_keys)


def cleanup_expired_uploads_global(
    db: Session,
    storage: StorageService,
    now: datetime | None = None,
) -> int:
    """Trusted maintenance cleanup across every project.

    Tenant requests still perform their own opportunistic cleanup, but this
    path is intended for a scheduler so an abandoned project cannot retain
    quarantine bytes indefinitely just because it never uploads again.
    """
    cutoff = now or _now()
    expired_ids = db.scalars(
        select(UploadSession.id).where(
            UploadSession.status.in_((UploadStatus.PENDING, UploadStatus.UPLOADING)),
            UploadSession.promotion_state != "PENDING",
            UploadSession.expires_at <= cutoff,
        )
    ).all()
    db.rollback()
    cleanup_keys: list[str] = []
    for session_id in expired_ids:
        with db.begin():
            upload = db.scalar(
                select(UploadSession)
                .where(UploadSession.id == session_id)
                .with_for_update()
            )
            if (
                upload is not None
                and upload.promotion_state != "PENDING"
                and upload.status in {UploadStatus.PENDING, UploadStatus.UPLOADING}
                and _is_expired(upload, cutoff)
            ):
                upload.status = UploadStatus.ABORTED
                if upload.quarantine_key:
                    cleanup_keys.append(upload.quarantine_key)
    for key in cleanup_keys:
        storage.delete_object(key)
    return len(cleanup_keys)


def reconcile_pending_upload_promotions(db: Session, storage: StorageService) -> int:
    """Finish validated PENDING promotions after process crashes or outages."""
    pending_ids = db.scalars(
        select(UploadSession.id).where(
            UploadSession.promotion_state == "PENDING",
            UploadSession.final_key.is_not(None),
            UploadSession.media_asset_id.is_not(None),
            UploadSession.mix_id.is_not(None),
        )
    ).all()
    db.rollback()
    completed = 0
    for session_id in pending_ids:
        with db.begin():
            upload = db.scalar(
                select(UploadSession)
                .where(UploadSession.id == session_id)
                .with_for_update()
            )
            if (
                upload is None
                or upload.promotion_state != "PENDING"
                or not upload.final_key
            ):
                continue
            quarantine_key, final_key = upload.quarantine_key, upload.final_key
        try:
            if storage.object_exists(final_key):
                storage.delete_object(quarantine_key)
            else:
                storage.promote(quarantine_key, final_key)
        except OSError:
            continue
        with db.begin():
            upload = db.scalar(
                select(UploadSession)
                .where(UploadSession.id == session_id)
                .with_for_update()
            )
            if (
                upload is None
                or upload.promotion_state != "PENDING"
                or upload.final_key != final_key
            ):
                continue
            mix = db.get(Mix, upload.mix_id)
            if mix is None or not storage.object_exists(final_key):
                continue
            mix.status = "ready"
            upload.status = UploadStatus.COMPLETED
            upload.promotion_state = "PROMOTED"
            completed += 1
    return completed
