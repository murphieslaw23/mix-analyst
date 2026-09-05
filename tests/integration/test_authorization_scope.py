"""Integration coverage for authenticated project ownership boundaries."""

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.session import Base, get_db
from api.app.main import app
from api.app.models.identity import Project, User
from api.app.models.job import Job, JobStatus, JobType
from api.app.models.mastering import MasteringPreset
from api.app.models.media import MediaAsset, Mix, UploadSession, UploadStatus
from api.app.models.outbox import OutboxMessage
from api.app.models.artifact import Artifact
from api.app.services.audio_probe import AudioProbeResult
from api.app.services.storage import StorageService


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


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


def test_job_list_is_paginated_and_never_discloses_another_project(client, user_a_token, job):
    """The Jobs screen may enumerate only durable jobs in the token project."""
    test_client, session_factory = client
    db = session_factory()
    try:
        db.add_all(
            [
                Job(
                    id="job-a-old", project_id="project-a", mix_id="mix-a", job_type=JobType.MASTERING,
                    status=JobStatus.QUEUED, progress_percent=0.0, created_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
                ),
                Job(
                    id="job-a-new", project_id="project-a", mix_id="mix-a", job_type=JobType.ANALYSIS,
                    status=JobStatus.RUNNING, progress_percent=50.0, created_at=datetime(2030, 1, 2, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    first_page = test_client.get("/api/v1/jobs?page=1&limit=1", headers={"Authorization": f"Bearer {user_a_token}"})
    assert first_page.status_code == 200
    assert first_page.json()["total"] == 2
    assert [item["id"] for item in first_page.json()["items"]] == ["job-a-new"]

    second_page = test_client.get("/api/v1/jobs?page=2&limit=1", headers={"Authorization": f"Bearer {user_a_token}"})
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()["items"]] == ["job-a-old"]
    assert job.id not in {item["id"] for item in first_page.json()["items"] + second_page.json()["items"]}


def test_job_list_cursor_keeps_a_complete_snapshot_during_concurrent_inserts(client, user_a_token, user_b_token):
    """A new queue item must not shift a cursor continuation past old work."""
    test_client, session_factory = client
    db = session_factory()
    try:
        db.add_all(
            [
                Job(id="cursor-old", project_id="project-a", mix_id="mix-a", job_type=JobType.ANALYSIS, status=JobStatus.QUEUED, progress_percent=0.0, created_at=datetime(2030, 1, 1, tzinfo=timezone.utc)),
                Job(id="cursor-middle", project_id="project-a", mix_id="mix-a", job_type=JobType.ANALYSIS, status=JobStatus.QUEUED, progress_percent=0.0, created_at=datetime(2030, 1, 2, tzinfo=timezone.utc)),
                Job(id="cursor-new", project_id="project-a", mix_id="mix-a", job_type=JobType.ANALYSIS, status=JobStatus.QUEUED, progress_percent=0.0, created_at=datetime(2030, 1, 3, tzinfo=timezone.utc)),
            ]
        )
        db.commit()
    finally:
        db.close()

    first_page = test_client.get("/api/v1/jobs?limit=2", headers={"Authorization": f"Bearer {user_a_token}"})
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert [item["id"] for item in first_body["items"]] == ["cursor-new", "cursor-middle"]
    assert first_body["total"] == 3
    assert isinstance(first_body["next_cursor"], str)

    # This is the queue entry that previously shifted offset page two and made
    # cursor-deduplicating clients skip `cursor-old` forever.
    db = session_factory()
    try:
        db.add(Job(id="cursor-arrived-later", project_id="project-a", mix_id="mix-a", job_type=JobType.MASTERING, status=JobStatus.QUEUED, progress_percent=0.0, created_at=datetime(2030, 1, 4, tzinfo=timezone.utc)))
        db.commit()
    finally:
        db.close()

    second_page = test_client.get(
        "/api/v1/jobs",
        params={"limit": 2, "cursor": first_body["next_cursor"]},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert [item["id"] for item in second_body["items"]] == ["cursor-old"]
    assert second_body["total"] == 3
    assert second_body["next_cursor"] is None
    assert "cursor-arrived-later" not in {item["id"] for item in first_body["items"] + second_body["items"]}

    # The opaque cursor is bound to the project that first received it.
    rejected = test_client.get(
        "/api/v1/jobs",
        params={"cursor": first_body["next_cursor"]},
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    assert rejected.status_code == 422

    malformed = test_client.get(
        "/api/v1/jobs",
        params={"cursor": "not-a-signed-cursor"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert malformed.status_code == 422


def test_signed_project_claim_requires_persisted_user_membership(client, user_b_mix):
    """A valid signature alone must not let a user select another persisted project."""
    test_client, _ = client
    mismatched_claim = _bearer_token("user-a", "project-b")

    response = test_client.get(
        f"/api/v1/mixes/{user_b_mix.id}",
        headers={"Authorization": f"Bearer {mismatched_claim}"},
    )

    assert response.status_code == 401


def test_authenticated_master_command_is_queued_until_worker_output_exists(client, user_a_token):
    """The mastering route creates a durable command, never a fake completion."""
    test_client, session_factory = client
    db = session_factory()
    try:
        media = MediaAsset(
            id="media-a",
            project_id="project-a",
            original_filename="owned.wav",
            storage_path="projects/project-a/artifacts/source/v1/" + "a" * 64,
            file_size_bytes=1,
            sha256_hash="a" * 64,
            duration_seconds=1.0,
            sample_rate=44100,
            channels=1,
            codec="pcm_s16le",
        )
        db.add(Mix(id="mix-a", project_id="project-a", title="Owned", media_asset=media, status="ready"))
        db.commit()
    finally:
        db.close()

    response = test_client.post(
        "/api/v1/mixes/mix-a/master",
        headers={"Authorization": f"Bearer {user_a_token}"},
        json={"target_lufs": -9.0, "true_peak_ceiling": -1.0},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["job_type"] == "MASTERING"
    assert body["parameters"]["target_lufs"] == -9.0
    assert body["parameters"]["true_peak_dbtp"] == -1.0
    assert body["parameters"]["preset_id"] == "sound_system_heavy"
    assert body["parameters"]["algorithm_version"] == "v1"
    db = session_factory()
    try:
        outbox = db.query(OutboxMessage).filter(OutboxMessage.aggregate_id == body["id"]).one()
        assert outbox.payload["task_name"] == "tasks.run_master_mix"
    finally:
        db.close()


def test_master_command_resolves_persisted_preset_before_queueing(client, user_a_token):
    """A selected preset supplies real parameters instead of silent scalar defaults."""
    test_client, session_factory = client
    db = session_factory()
    try:
        db.add(
            MasteringPreset(
                id="owned-club-profile",
                project_id="project-a",
                name="Owned club profile",
                target_lufs=-15.0,
                true_peak_ceiling=-1.4,
                target_lra=8.0,
                eq_settings={"sub_boost_db": 1.25},
                compressor_settings={"ratio": 2.25},
                is_builtin=False,
            )
        )
        media = MediaAsset(
            id="preset-media-a",
            project_id="project-a",
            original_filename="preset.wav",
            storage_path="projects/project-a/artifacts/source/v1/" + "9" * 64,
            file_size_bytes=1,
            sha256_hash="9" * 64,
            duration_seconds=1.0,
            sample_rate=44100,
            channels=1,
            codec="pcm_s16le",
        )
        db.add(Mix(id="preset-mix-a", project_id="project-a", title="Preset", media_asset=media, status="ready"))
        db.commit()
    finally:
        db.close()

    response = test_client.post(
        "/api/v1/mixes/preset-mix-a/master",
        headers={"Authorization": f"Bearer {user_a_token}"},
        json={"preset_id": "owned-club-profile"},
    )

    assert response.status_code == 202, response.text
    parameters = response.json()["parameters"]
    assert parameters == {
        "preset_id": "owned-club-profile",
        "preset_name": "Owned club profile",
        "target_lufs": -15.0,
        "true_peak_dbtp": -1.4,
        "target_lra": 8.0,
        "eq_settings": {"sub_boost_db": 1.25},
        "compressor_settings": {"ratio": 2.25},
        "algorithm_version": "v1",
    }


def test_master_command_rejects_unknown_selected_preset(client, user_a_token):
    test_client, _ = client
    response = test_client.post(
        "/api/v1/mixes/mix-a/master",
        headers={"Authorization": f"Bearer {user_a_token}"},
        json={"preset_id": "missing-preset"},
    )
    assert response.status_code == 404


def test_master_command_rejects_a_preset_owned_by_another_project(client, user_a_token):
    """A preset id is not a cross-project capability."""
    test_client, session_factory = client
    db = session_factory()
    try:
        db.add(
            MasteringPreset(
                id="project-b-profile",
                project_id="project-b",
                name="Private profile",
                target_lufs=-12.0,
                true_peak_ceiling=-1.0,
                target_lra=7.0,
                is_builtin=False,
            )
        )
        db.commit()
    finally:
        db.close()

    response = test_client.post(
        "/api/v1/mixes/mix-a/master",
        headers={"Authorization": f"Bearer {user_a_token}"},
        json={"preset_id": "project-b-profile"},
    )
    assert response.status_code == 404


def test_upgrade_preserves_unattributable_legacy_custom_preset_as_explicit_shared_profile(tmp_path):
    """Upgrade from the prior head must not make an old global custom preset unusable."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from api.app.schemas.auth import CurrentPrincipal
    from api.app.services.mastering_presets import resolve_mastering_parameters

    database_url = f"sqlite:///{tmp_path / 'legacy-presets.db'}"
    environment = os.environ | {"DATABASE_URL": database_url, "PYTHONPATH": str(REPOSITORY_ROOT)}
    previous = "20260903_10_final_core_repair"
    upgrade = [sys.executable, "-m", "alembic", "-c", "api/alembic.ini", "upgrade"]
    assert subprocess.run(
        [*upgrade, previous], cwd=REPOSITORY_ROOT, env=environment, capture_output=True, text=True
    ).returncode == 0

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO mastering_presets (id, name, is_builtin) VALUES ('legacy-custom', 'Legacy Custom', 0)")
        )

    result = subprocess.run([*upgrade, "head"], cwd=REPOSITORY_ROOT, env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with Session(engine) as session:
        preset = session.get(MasteringPreset, "legacy-custom")
        assert preset is not None
        assert preset.project_id is None
        assert preset.is_legacy_shared is True
        resolved = resolve_mastering_parameters(
            session,
            CurrentPrincipal(user_id="user-a", project_id="project-a"),
            "legacy-custom",
            target_lufs=None,
            true_peak_dbtp=None,
        )
        assert resolved["preset_id"] == "legacy-custom"


def test_mix_artifacts_are_presented_as_owner_scoped_metadata(client, user_a_token):
    """Artifact responses expose an API download route, never a host path."""
    test_client, session_factory = client
    db = session_factory()
    try:
        media = MediaAsset(
            id="artifact-media-a", project_id="project-a", original_filename="Owned Mix.wav",
            storage_path="projects/project-a/artifacts/source/v1/" + "c" * 64,
            file_size_bytes=4, sha256_hash="c" * 64, duration_seconds=1.0,
            sample_rate=44100, channels=1, codec="pcm_s16le",
        )
        mix = Mix(id="artifact-mix-a", project_id="project-a", title="Owned", media_asset=media, status="ready")
        db.add(mix)
        db.flush()
        db.add_all(
            [
                Artifact(
                    id="artifact-source-a", project_id="project-a", mix_id=mix.id, role="source",
                    key=media.storage_path, sha256="c" * 64, algorithm_version="v1", media_type="audio/wav", byte_length=4,
                ),
                Artifact(
                    id="artifact-metadata-a", project_id="project-a", mix_id=mix.id, role="metadata",
                    key="projects/project-a/artifacts/metadata/v1/" + "c" * 64, sha256="d" * 64,
                    algorithm_version="v1", media_type="application/json", byte_length=4,
                    report={"suggested_download_name": "Owned Mix [Tekno].wav", "genre": "Tekno"},
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    response = test_client.get(
        "/api/v1/mixes/artifact-mix-a", headers={"Authorization": f"Bearer {user_a_token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suggested_download_name"] == "Owned Mix [Tekno].wav"
    source = next(item for item in body["artifacts"] if item["role"] == "source")
    assert source["key"].startswith("projects/project-a/")
    assert source["download_url"] == "/api/v1/mixes/artifact-mix-a/artifacts/artifact-source-a/download"
    assert "/tmp/" not in source["download_url"]


def test_artifact_download_uses_role_specific_names_without_weakening_project_scope(client, user_a_token, user_b_token, monkeypatch, tmp_path):
    """Source downloads retain the upload name; mastered output uses its suggested name."""
    storage = StorageService(str(tmp_path / "storage"))
    monkeypatch.setattr("api.app.api.v1.mixes.settings.storage_root", str(tmp_path / "storage"))
    test_client, session_factory = client
    source_key = "projects/project-a/artifacts/source/v1/" + "a" * 64
    mastered_key = "projects/project-a/artifacts/mastered/v1/" + "b" * 64
    db = session_factory()
    try:
        media = MediaAsset(
            id="download-media-a", project_id="project-a", original_filename="Floor Tool 01.aiff",
            storage_path=source_key, file_size_bytes=4, sha256_hash="a" * 64, duration_seconds=1.0,
            sample_rate=44100, channels=2, codec="pcm_s16le",
        )
        mix = Mix(id="download-mix-a", project_id="project-a", title="Download names", media_asset=media, status="ready")
        db.add(mix)
        db.flush()
        db.add_all([
            Artifact(id="download-source-a", project_id="project-a", mix_id=mix.id, role="source", key=source_key, sha256="a" * 64, algorithm_version="v1", media_type="audio/aiff", byte_length=4),
            Artifact(id="download-mastered-a", project_id="project-a", mix_id=mix.id, role="mastered", key=mastered_key, sha256="b" * 64, algorithm_version="v1", media_type="audio/wav", byte_length=4),
            Artifact(id="download-metadata-a", project_id="project-a", mix_id=mix.id, role="metadata", key="projects/project-a/artifacts/metadata/v1/" + "c" * 64, sha256="c" * 64, algorithm_version="v1", media_type="application/json", byte_length=2, report={"suggested_download_name": "Floor Tool 01 [SYCO23 Master].wav"}),
        ])
        db.commit()
    finally:
        db.close()

    for key, contents in ((source_key, b"src!"), (mastered_key, b"mast")):
        path = storage.object_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)

    headers = {"Authorization": f"Bearer {user_a_token}"}
    source = test_client.get("/api/v1/mixes/download-mix-a/artifacts/download-source-a/download", headers=headers)
    mastered = test_client.get("/api/v1/mixes/download-mix-a/artifacts/download-mastered-a/download", headers=headers)
    foreign = test_client.get("/api/v1/mixes/download-mix-a/artifacts/download-mastered-a/download", headers={"Authorization": f"Bearer {user_b_token}"})

    assert source.status_code == 200
    assert f"filename*=utf-8''{quote('Floor Tool 01.aiff')}" in source.headers["content-disposition"]
    assert mastered.status_code == 200
    assert f"filename*=utf-8''{quote('Floor Tool 01 [SYCO23 Master].wav')}" in mastered.headers["content-disposition"]
    assert foreign.status_code == 404

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
