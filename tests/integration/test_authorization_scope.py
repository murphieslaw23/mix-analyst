"""Integration coverage for authenticated project ownership boundaries."""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.session import Base, get_db
from api.app.main import app
from api.app.models.identity import Project, User
from api.app.models.job import Job, JobStatus, JobType
from api.app.models.media import MediaAsset, Mix, UploadSession, UploadStatus
from api.app.services.audio_probe import AudioProbeResult
from api.app.services.storage import StorageService


def _bearer_token(user_id: str, project_id: str) -> str:
    """Make a fixed HS256 token independently of the auth implementation."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=")
    claims = json.dumps({"sub": user_id, "project_id": project_id}, separators=(",", ":")).encode()
    payload = base64.urlsafe_b64encode(claims).rstrip(b"=")
    signature = hmac.new(b"development-only-secret-change-me-32", header + b"." + payload, hashlib.sha256).digest()
    return b".".join((header, payload, base64.urlsafe_b64encode(signature).rstrip(b"="))).decode()


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client, session_factory
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


@pytest.fixture
def user_b_mix(client):
    _, session_factory = client
    db = session_factory()
    try:
        media = MediaAsset(
            id="media-b",
            original_filename="other-user.wav",
            storage_path="media-b.wav",
            file_size_bytes=1,
            sha256_hash="b" * 64,
            duration_seconds=1.0,
            sample_rate=44100,
            channels=2,
            codec="pcm_s16le",
        )
        mix = Mix(
            id="mix-b",
            title="Other user's mix",
            media_asset=media,
            status="ready",
        )
        # This attribute becomes a persisted ownership column in Task 2.  It is
        # deliberately harmless to the pre-identity baseline so this test first
        # demonstrates its current global-access failure.
        media.project_id = "project-b"
        mix.project_id = "project-b"
        db.add(mix)
        db.commit()
        return mix
    finally:
        db.close()


@pytest.fixture
def job(client, user_b_mix):
    _, session_factory = client
    db = session_factory()
    try:
        job = Job(
            id="job-b",
            mix_id=user_b_mix.id,
            job_type=JobType.ANALYSIS,
            status=JobStatus.QUEUED,
            progress_percent=0.0,
            created_at=datetime.now(timezone.utc),
        )
        job.project_id = "project-b"
        db.add(job)
        db.commit()
        return job
    finally:
        db.close()


@pytest.fixture
def user_b_upload(client, tmp_path):
    _, session_factory = client
    upload_file = tmp_path / "other-user.wav"
    upload_file.write_bytes(b"audio")
    db = session_factory()
    try:
        upload_session = UploadSession(
            id="upload-b",
            filename="other-user.wav",
            total_size_bytes=5,
            bytes_received=5,
            chunk_size=5,
            temp_path=str(upload_file),
            status=UploadStatus.UPLOADING,
        )
        upload_session.project_id = "project-b"
        db.add(upload_session)
        db.commit()
        return upload_session
    finally:
        db.close()


def test_user_cannot_read_another_users_mix(client, user_a_token, user_b_mix):
    test_client, _ = client
    response = test_client.get(
        f"/api/v1/mixes/{user_b_mix.id}",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 404


def test_unauthenticated_job_event_stream_is_rejected(client, job, monkeypatch):
    async def one_event(_job_id):
        yield "event: connect\\ndata: {}\\n\\n"

    monkeypatch.setattr("api.app.api.v1.jobs.stream_job_events", one_event)
    test_client, _ = client
    response = test_client.get(f"/api/v1/jobs/{job.id}/events")
    assert response.status_code == 401


def test_user_cannot_read_another_users_upload_session(client, user_a_token, user_b_upload):
    test_client, _ = client
    response = test_client.get(
        f"/api/v1/{user_b_upload.id}",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 404


def test_unauthenticated_upload_status_is_rejected(client, user_b_upload):
    test_client, _ = client
    response = test_client.get(f"/api/v1/{user_b_upload.id}")
    assert response.status_code == 401


def test_unauthenticated_upload_initialization_is_rejected(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "api.app.api.v1.uploads.storage.create_upload_session_file",
        lambda _session_id: tmp_path / "unauthenticated-upload.tmp",
    )
    test_client, _ = client
    response = test_client.post(
        "/api/v1",
        json={"filename": "unauthenticated.wav", "total_size_bytes": 5, "chunk_size": 5},
    )
    assert response.status_code == 401


def test_user_cannot_append_to_another_users_upload_session(client, user_a_token, user_b_upload):
    test_client, _ = client
    response = test_client.patch(
        f"/api/v1/{user_b_upload.id}",
        headers={"Authorization": f"Bearer {user_a_token}"},
        data={"offset": "5"},
        files={"file": ("chunk.wav", b"x", "audio/wav")},
    )
    assert response.status_code == 404


def test_upload_completion_assigns_the_principal_project(client, user_b_token, monkeypatch, tmp_path):
    monkeypatch.setattr("api.app.api.v1.uploads.storage", StorageService(str(tmp_path / "storage")))
    monkeypatch.setattr(
        "api.app.services.upload_sessions.probe_audio",
        lambda _path: AudioProbeResult(
            duration_seconds=1.0,
            sample_rate=44100,
            channels=2,
            codec="pcm_s16le",
        ),
    )

    test_client, session_factory = client
    initialized = test_client.post(
        "/api/v1",
        headers={"Authorization": f"Bearer {user_b_token}"},
        json={"filename": "other-user.wav", "total_size_bytes": 5, "content_type": "audio/wav"},
    )
    assert initialized.status_code == 201
    upload = initialized.json()
    appended = test_client.patch(
        upload["upload_url"],
        headers={"Authorization": f"Bearer {user_b_token}", "Upload-Offset": "0"},
        content=b"audio",
    )
    assert appended.status_code == 200
    response = test_client.post(
        f"{upload['upload_url']}/complete",
        headers={"Authorization": f"Bearer {user_b_token}"},
        json={"title": "Owned mix"},
    )

    assert response.status_code == 200
    db = session_factory()
    try:
        media = db.query(MediaAsset).filter(MediaAsset.id == response.json()["media_asset_id"]).one()
        mix = db.query(Mix).filter(Mix.id == response.json()["mix_id"]).one()
        assert media.project_id == "project-b"
        assert mix.project_id == "project-b"
    finally:
        db.close()
