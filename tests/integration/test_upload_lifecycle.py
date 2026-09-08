"""Integration coverage for the bounded, project-owned upload lifecycle.

Each test names the broken lifecycle transition it protects: accepting an
oversized body, trusting a stale client offset, finalizing an invalid or
expired upload, or exposing a project-owned object outside its scope.
"""

import base64
import hashlib
import hmac
import io
import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.api.v1 import uploads as upload_routes
from api.app.db.session import Base, get_db
from api.app.main import app
from api.app.models.identity import Project, User
from api.app.models.media import MediaAsset, Mix, UploadSession, UploadStatus
from api.app.schemas.auth import CurrentPrincipal
from api.app.services.audio_probe import AudioProbeError, AudioProbeResult
from api.app.services.storage import StorageService, derived_object_key
from api.app.services.upload_sessions import finalize_upload


def _bearer_token(user_id: str, project_id: str) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=")
    claims = json.dumps(
        {"sub": user_id, "project_id": project_id}, separators=(",", ":")
    ).encode()
    payload = base64.urlsafe_b64encode(claims).rstrip(b"=")
    signature = hmac.new(
        b"development-only-secret-change-me-32", header + b"." + payload, hashlib.sha256
    ).digest()
    return b".".join(
        (header, payload, base64.urlsafe_b64encode(signature).rstrip(b"="))
    ).decode()


@pytest.fixture
def lifecycle_client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
    )
    Base.metadata.create_all(bind=engine)
    db = session_factory()
    try:
        db.add_all(
            [
                User(id="user-a"),
                User(id="user-b"),
                Project(id="project-a", owner_id="user-a"),
                Project(id="project-b", owner_id="user-b"),
            ]
        )
        db.commit()
    finally:
        db.close()

    storage = StorageService(str(tmp_path / "storage"))
    monkeypatch.setattr(upload_routes, "storage", storage)
    monkeypatch.setattr(
        upload_routes,
        "settings",
        SimpleNamespace(
            max_upload_size_bytes=1024,
            max_chunk_size_bytes=4,
            default_chunk_size_bytes=4,
            upload_session_ttl_seconds=60,
        ),
    )

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client, session_factory, storage
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def user_a_token():
    return _bearer_token("user-a", "project-a")


@pytest.fixture
def user_b_token():
    return _bearer_token("user-b", "project-b")


def _start_upload(
    client, token, *, filename="mix.wav", size=4, content_type="audio/wav"
):
    response = client.post(
        "/api/v1",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "filename": filename,
            "total_size_bytes": size,
            "content_type": content_type,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_chunk_larger_than_configured_limit_is_rejected(lifecycle_client, user_a_token):
    """Removing the streaming bound would accept this five-byte body."""
    client, _, _ = lifecycle_client
    upload = _start_upload(client, user_a_token, size=5)

    response = client.patch(
        upload["upload_url"],
        headers={"Authorization": f"Bearer {user_a_token}", "Upload-Offset": "0"},
        content=b"xxxxx",
    )

    assert response.status_code == 413


def test_stale_offset_returns_conflict(lifecycle_client, user_a_token):
    """Replacing the locked database offset with a client value would accept the retry."""
    client, _, _ = lifecycle_client
    upload = _start_upload(client, user_a_token, size=4)
    headers = {"Authorization": f"Bearer {user_a_token}", "Upload-Offset": "0"}

    first = client.patch(upload["upload_url"], headers=headers, content=b"abcd")
    stale = client.patch(upload["upload_url"], headers=headers, content=b"x")

    assert first.status_code == 200, first.text
    assert stale.status_code == 409


def test_retry_reconciles_file_ahead_of_committed_offset(
    lifecycle_client, user_a_token
):
    """A crash after fsync but before the offset commit must not wedge the upload."""
    client, session_factory, storage = lifecycle_client
    upload = _start_upload(client, user_a_token, size=4)
    db = session_factory()
    try:
        quarantine_key = db.get(UploadSession, upload["upload_id"]).quarantine_key
    finally:
        db.close()

    # Model a process death after bytes reached durable storage but before the
    # database transaction advanced its authoritative offset.
    storage.write_limited_chunk(quarantine_key, io.BytesIO(b"ab"), 4)
    response = client.patch(
        upload["upload_url"],
        headers={"Authorization": f"Bearer {user_a_token}", "Upload-Offset": "0"},
        content=b"abcd",
    )

    assert response.status_code == 200, response.text
    assert response.json()["offset"] == 4
    assert storage.object_path(quarantine_key).read_bytes() == b"abcd"


def test_finalization_promotes_validated_quarantine_object_to_derived_key(
    lifecycle_client, user_a_token, monkeypatch
):
    """Replacing server-derived promotion with a client path would fail this ownership/key assertion."""
    client, session_factory, storage = lifecycle_client
    upload = _start_upload(client, user_a_token, filename="set.wav", size=4)
    monkeypatch.setattr(
        "api.app.services.upload_sessions.probe_audio",
        lambda _path: AudioProbeResult(
            duration_seconds=1.0, sample_rate=44100, channels=2, codec="pcm_s16le"
        ),
    )

    append = client.patch(
        upload["upload_url"],
        headers={"Authorization": f"Bearer {user_a_token}", "Upload-Offset": "0"},
        content=b"abcd",
    )
    complete = client.post(
        f"{upload['upload_url']}/complete",
        headers={"Authorization": f"Bearer {user_a_token}"},
        json={"title": "Set"},
    )

    assert append.status_code == 200, append.text
    assert complete.status_code == 200, complete.text
    expected_sha = hashlib.sha256(b"abcd").hexdigest()
    expected_key = f"projects/project-a/artifacts/source/v1/{expected_sha}"
    db = session_factory()
    try:
        session = db.get(UploadSession, upload["upload_id"])
        assert session.status is UploadStatus.COMPLETED
        assert session.quarantine_key != expected_key
        assert not storage.object_exists(session.quarantine_key)
        assert storage.object_exists(expected_key)
        assert complete.json()["sha256_hash"] == expected_sha
    finally:
        db.close()


def test_finalization_resumes_database_pending_object_promotion(
    lifecycle_client, user_a_token, monkeypatch
):
    """A crash after DB prepare must resume without exposing or deleting the result rows."""
    client, session_factory, storage = lifecycle_client
    upload = _start_upload(client, user_a_token, filename="recover.wav", size=4)
    monkeypatch.setattr(
        "api.app.services.upload_sessions.probe_audio",
        lambda _path: AudioProbeResult(
            duration_seconds=1.0, sample_rate=44100, channels=2, codec="pcm_s16le"
        ),
    )
    appended = client.patch(
        upload["upload_url"],
        headers={"Authorization": f"Bearer {user_a_token}", "Upload-Offset": "0"},
        content=b"data",
    )
    assert appended.status_code == 200, appended.text

    real_promote = storage.promote
    promotion_attempts = 0

    def crash_once(quarantine_key, final_key):
        nonlocal promotion_attempts
        promotion_attempts += 1
        if promotion_attempts == 1:
            raise OSError("simulated process loss before promotion")
        return real_promote(quarantine_key, final_key)

    monkeypatch.setattr(storage, "promote", crash_once)
    db = session_factory()
    principal = CurrentPrincipal(user_id="user-a", project_id="project-a")
    try:
        with pytest.raises(Exception, match="promote validated upload"):
            finalize_upload(db, principal, upload["upload_id"], storage)
        db.expire_all()
        pending = db.get(UploadSession, upload["upload_id"])
        assert pending.promotion_state == "PENDING"
        assert pending.status is not UploadStatus.COMPLETED
        assert db.get(Mix, pending.mix_id).status == "finalizing"
        assert not storage.object_exists(pending.final_key)

        recovered = finalize_upload(db, principal, upload["upload_id"], storage)
        assert recovered.mix.status == "ready"
        assert storage.object_exists(pending.final_key)
        db.expire_all()
        assert (
            db.get(UploadSession, upload["upload_id"]).status is UploadStatus.COMPLETED
        )
    finally:
        db.close()


def test_same_project_duplicate_finalization_reuses_asset_and_cleans_redundant_quarantine(
    lifecycle_client, user_a_token, monkeypatch
):
    """Dropping final-key deduplication creates two assets or leaves the second quarantine object."""
    client, session_factory, storage = lifecycle_client
    monkeypatch.setattr(
        "api.app.services.upload_sessions.probe_audio",
        lambda _path: AudioProbeResult(
            duration_seconds=1.0, sample_rate=44100, channels=2, codec="pcm_s16le"
        ),
    )
    first = _start_upload(client, user_a_token, filename="first.wav", size=4)
    second = _start_upload(client, user_a_token, filename="second.wav", size=4)
    for upload in (first, second):
        appended = client.patch(
            upload["upload_url"],
            headers={"Authorization": f"Bearer {user_a_token}", "Upload-Offset": "0"},
            content=b"same",
        )
        assert appended.status_code == 200, appended.text

    first_complete = client.post(
        f"{first['upload_url']}/complete",
        headers={"Authorization": f"Bearer {user_a_token}"},
        json={"title": "First"},
    )
    second_complete = client.post(
        f"{second['upload_url']}/complete",
        headers={"Authorization": f"Bearer {user_a_token}"},
        json={"title": "Second"},
    )

    assert first_complete.status_code == 200, first_complete.text
    assert second_complete.status_code == 200, second_complete.text
    assert (
        first_complete.json()["media_asset_id"]
        == second_complete.json()["media_asset_id"]
    )
    db = session_factory()
    try:
        second_session = db.get(UploadSession, second["upload_id"])
        assert db.query(MediaAsset).count() == 1
        assert db.query(Mix).count() == 2
        assert second_session.status is UploadStatus.COMPLETED
        assert not storage.object_exists(second_session.quarantine_key)
    finally:
        db.close()


def test_finalization_recovers_from_same_final_key_insert_race(
    lifecycle_client, user_a_token, monkeypatch
):
    """Removing the savepoint/reload path turns a concurrent winner into a 500 and leaked quarantine object."""
    client, session_factory, storage = lifecycle_client
    monkeypatch.setattr(
        "api.app.services.upload_sessions.probe_audio",
        lambda _path: AudioProbeResult(
            duration_seconds=1.0, sample_rate=44100, channels=2, codec="pcm_s16le"
        ),
    )
    upload = _start_upload(client, user_a_token, size=4)
    appended = client.patch(
        upload["upload_url"],
        headers={"Authorization": f"Bearer {user_a_token}", "Upload-Offset": "0"},
        content=b"race",
    )
    assert appended.status_code == 200, appended.text

    sha256_hash = hashlib.sha256(b"race").hexdigest()
    final_key = derived_object_key("project-a", sha256_hash, "source", "v1")
    db = session_factory()
    try:
        session = db.get(UploadSession, upload["upload_id"])
        quarantine_key = session.quarantine_key
        db.rollback()
        final_path = storage.path_for_key(final_key)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        os.link(storage.path_for_key(quarantine_key), final_path)

        original_begin_nested = db.begin_nested

        def winner_arrives_after_initial_lookup():
            db.execute(
                MediaAsset.__table__.insert().values(
                    id="concurrent-winner",
                    project_id="project-a",
                    original_filename="winner.wav",
                    storage_path=final_key,
                    file_size_bytes=4,
                    sha256_hash=sha256_hash,
                    mime_type="audio/wav",
                    duration_seconds=1.0,
                    sample_rate=44100,
                    channels=2,
                    codec="pcm_s16le",
                )
            )
            return original_begin_nested()

        monkeypatch.setattr(db, "begin_nested", winner_arrives_after_initial_lookup)
        finalized = finalize_upload(
            db,
            CurrentPrincipal(user_id="user-a", project_id="project-a"),
            upload["upload_id"],
            storage,
        )

        assert finalized.media_asset.id == "concurrent-winner"
        assert finalized.mix.media_asset_id == "concurrent-winner"
        assert not storage.object_exists(quarantine_key)
        assert storage.object_exists(final_key)
    finally:
        db.close()


def test_expired_session_is_aborted_and_quarantine_is_cleaned(
    lifecycle_client, user_a_token
):
    """Removing expiry cleanup would leave an upload writable and its object present."""
    client, session_factory, storage = lifecycle_client
    upload = _start_upload(client, user_a_token, size=4)
    db = session_factory()
    try:
        session = db.get(UploadSession, upload["upload_id"])
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        quarantine_key = session.quarantine_key
        db.commit()
    finally:
        db.close()

    response = client.patch(
        upload["upload_url"],
        headers={"Authorization": f"Bearer {user_a_token}", "Upload-Offset": "0"},
        content=b"abcd",
    )
    assert response.status_code == 410
    assert not storage.object_exists(quarantine_key)
    db = session_factory()
    try:
        assert db.get(UploadSession, upload["upload_id"]).status is UploadStatus.ABORTED
    finally:
        db.close()


def test_trusted_global_cleanup_removes_expired_quarantine_across_projects(
    lifecycle_client, user_a_token, user_b_token
):
    """Cleanup must not depend on a tenant happening to start another upload."""
    from api.app.services.upload_sessions import cleanup_expired_uploads_global

    client, session_factory, storage = lifecycle_client
    uploads = [
        _start_upload(client, user_a_token, filename="a.wav", size=4),
        _start_upload(client, user_b_token, filename="b.wav", size=4),
    ]
    db = session_factory()
    try:
        keys = []
        for upload in uploads:
            persisted = db.get(UploadSession, upload["upload_id"])
            persisted.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            keys.append(persisted.quarantine_key)
        db.commit()

        assert cleanup_expired_uploads_global(db, storage) == 2
        assert all(
            db.get(UploadSession, upload["upload_id"]).status is UploadStatus.ABORTED
            for upload in uploads
        )
        assert all(not storage.object_exists(key) for key in keys)
    finally:
        db.close()


def test_audio_probe_details_are_not_returned_to_upload_client(
    lifecycle_client, user_a_token, monkeypatch
):
    """Absolute paths and raw ffprobe stderr are server-only diagnostics."""
    client, _, _ = lifecycle_client
    upload = _start_upload(client, user_a_token, filename="invalid.wav", size=4)
    appended = client.patch(
        upload["upload_url"],
        headers={"Authorization": f"Bearer {user_a_token}", "Upload-Offset": "0"},
        content=b"nope",
    )
    assert appended.status_code == 200, appended.text
    monkeypatch.setattr(
        "api.app.services.upload_sessions.probe_audio",
        lambda _path: (_ for _ in ()).throw(
            AudioProbeError(
                "ffprobe failed for /storage/projects/secret.wav: private decoder stderr"
            )
        ),
    )

    response = client.post(
        f"{upload['upload_url']}/complete",
        headers={"Authorization": f"Bearer {user_a_token}"},
        json={},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Uploaded file is not valid audio"
    assert "/storage/" not in response.text
    assert "decoder stderr" not in response.text


def test_new_upload_does_not_cleanup_expired_session_from_another_project(
    lifecycle_client, user_a_token, user_b_token
):
    """Removing the cleanup project predicate aborts and deletes B's upload when A starts one."""
    client, session_factory, storage = lifecycle_client
    upload_b = _start_upload(client, user_b_token, size=4)
    db = session_factory()
    try:
        session_b = db.get(UploadSession, upload_b["upload_id"])
        session_b.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        quarantine_key_b = session_b.quarantine_key
        db.commit()
    finally:
        db.close()

    _start_upload(client, user_a_token, size=4)

    db = session_factory()
    try:
        assert (
            db.get(UploadSession, upload_b["upload_id"]).status is UploadStatus.PENDING
        )
    finally:
        db.close()
    assert storage.object_exists(quarantine_key_b)


def test_cross_project_upload_session_remains_not_found(
    lifecycle_client, user_a_token, user_b_token
):
    """Dropping the project predicate would disclose this other project's session."""
    client, _, _ = lifecycle_client
    upload = _start_upload(client, user_b_token, size=4)

    response = client.get(
        upload["upload_url"], headers={"Authorization": f"Bearer {user_a_token}"}
    )

    assert response.status_code == 404
