"""Stale upload-session purge behavior."""
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from api.app.models.media import UploadSession, UploadStatus
from api.app.api.v1.uploads import purge_stale_uploads
from tests.helpers.pipeline_seed import make_session


def _add_session(db, sid, status, age_hours, storage_root, with_file=True):
    tmp = storage_root / "quarantine" / f"upload_{sid}.tmp"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if with_file:
        tmp.write_bytes(b"partial-bytes")
    db.add(
        UploadSession(
            id=sid,
            filename="set.wav",
            total_size_bytes=1000,
            bytes_received=100,
            temp_path=str(tmp),
            status=status,
        )
    )
    db.commit()
    # Backdate bypassing the auto onupdate hook.
    old = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    db.execute(
        text("UPDATE upload_sessions SET updated_at = :t WHERE id = :id"),
        {"t": old, "id": sid},
    )
    db.commit()
    return tmp


def test_purge_removes_only_expired_unfinished_sessions(tmp_path):
    db = make_session(tmp_path)
    storage_root = tmp_path / "storage"
    storage_root.mkdir()

    old_pending = _add_session(db, "old-pending", UploadStatus.PENDING, 30, storage_root)
    old_failed = _add_session(db, "old-failed", UploadStatus.FAILED, 30, storage_root)
    fresh = _add_session(db, "fresh", UploadStatus.UPLOADING, 1, storage_root)
    done = _add_session(db, "done", UploadStatus.COMPLETED, 72, storage_root)
    orphan = storage_root / "quarantine" / "upload_orphan.tmp"
    orphan.write_bytes(b"orphan")
    import os

    ancient = datetime.now(timezone.utc).timestamp() - 100 * 3600
    os.utime(orphan, (ancient, ancient))

    removed = purge_stale_uploads(db, max_age_hours=24, storage_root=str(storage_root))

    assert removed == 2
    remaining = {row.id for row in db.query(UploadSession).all()}
    assert remaining == {"fresh", "done"}
    assert not old_pending.exists()
    assert not old_failed.exists()
    assert fresh.exists()
    assert done.exists()
    assert not orphan.exists()
