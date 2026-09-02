"""Integration coverage for the bounded, project-owned upload lifecycle.

Each test names the broken lifecycle transition it protects: accepting an
oversized body, trusting a stale client offset, finalizing an invalid or
expired upload, or exposing a project-owned object outside its scope.
"""

import base64
import hashlib
import hmac
import json
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
from api.app.models.media import UploadSession, UploadStatus
from api.app.services.audio_probe import AudioProbeResult
from api.app.services.storage import StorageService


def _bearer_token(user_id: str, project_id: str) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=")
    claims = json.dumps({"sub": user_id, "project_id": project_id}, separators=(",", ":")).encode()
    payload = base64.urlsafe_b64encode(claims).rstrip(b"=")
    signature = hmac.new(b"development-only-secret-change-me-32", header + b"." + payload, hashlib.sha256).digest()
    return b".".join((header, payload, base64.urlsafe_b64encode(signature).rstrip(b"="))).decode()


@pytest.fixture
def lifecycle_client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
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


def _start_upload(client, token, *, filename="mix.wav", size=4, content_type="audio/wav"):
    response = client.post(
        "/api/v1",
        headers={"Authorization": f"Bearer {token}"},
        json={"filename": filename, "total_size_bytes": size, "content_type": content_type},
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


def test_finalization_promotes_validated_quarantine_object_to_derived_key(lifecycle_client, user_a_token, monkeypatch):
    """Replacing server-derived promotion with a client path would fail this ownership/key assertion."""
    client, session_factory, storage = lifecycle_client
    upload = _start_upload(client, user_a_token, filename="set.wav", size=4)
    monkeypatch.setattr(
        "api.app.services.upload_sessions.probe_audio",
        lambda _path: AudioProbeResult(duration_seconds=1.0, sample_rate=44100, channels=2, codec="pcm_s16le"),
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


def test_expired_session_is_aborted_and_quarantine_is_cleaned(lifecycle_client, user_a_token):
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


def test_cross_project_upload_session_remains_not_found(lifecycle_client, user_a_token, user_b_token):
    """Dropping the project predicate would disclose this other project's session."""
    client, _, _ = lifecycle_client
    upload = _start_upload(client, user_b_token, size=4)

    response = client.get(upload["upload_url"], headers={"Authorization": f"Bearer {user_a_token}"})

    assert response.status_code == 404
