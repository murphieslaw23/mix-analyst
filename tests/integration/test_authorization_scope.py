"""Authenticated project ownership boundaries (core plan Task 2)."""

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.app.main as main_mod
from api.app import models as models  # noqa: PLC0414  (registers metadata)
from api.app.config import settings
from api.app.db.session import Base, get_db
from api.app.main import app
from api.app.models.identity import Project, User
from api.app.models.job import Job
from api.app.models.media import MediaAsset, Mix
from tests.helpers.pipeline_seed import seed_job

TEST_SECRET = "test-only-secret-at-least-32-chars-long"


def _bearer(user_id: str, project_id: str) -> dict[str, str]:
    token = jwt.encode(
        {"sub": user_id, "project_id": project_id}, TEST_SECRET, algorithm="HS256"
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_asset_mix(db, *, asset_id, mix_id, project_id):
    db.add(
        MediaAsset(
            id=asset_id,
            project_id=project_id,
            original_filename="set.wav",
            storage_path=f"assets/audio/{asset_id}.wav",
            file_size_bytes=8,
            sha256_hash="0" * 64,
            duration_seconds=10.0,
            sample_rate=44100,
            channels=2,
            codec="pcm",
        )
    )
    db.add(
        Mix(
            id=mix_id,
            title="T",
            project_id=project_id,
            media_asset_id=asset_id,
            status="ready",
        )
    )
    db.commit()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "auth_jwt_secret", TEST_SECRET)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_factory()
    db.add_all(
        [
            User(id="user-a"),
            User(id="user-b"),
            User(id="default-user"),
            Project(id="project-a", owner_id="user-a"),
            Project(id="project-b", owner_id="user-b"),
            Project(id="default-project", owner_id="default-user"),
        ]
    )
    db.commit()
    _seed_asset_mix(db, asset_id="ab", mix_id="mix-b", project_id="project-b")
    _seed_asset_mix(db, asset_id="ad", mix_id="mix-d", project_id="default-project")
    seed_job(db, "job-b", "mix-b")
    db.execute(update(Job).where(Job.id == "job-b").values(project_id="project-b"))
    db.commit()
    db.close()

    monkeypatch.setattr(main_mod, "init_db", lambda: None)
    app.dependency_overrides[get_db] = lambda: session_factory()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_user_cannot_read_another_users_mix(client):
    res = client.get("/api/v1/mixes/mix-b", headers=_bearer("user-a", "project-a"))
    assert res.status_code == 404


def test_owner_can_read_own_mix(client):
    res = client.get("/api/v1/mixes/mix-b", headers=_bearer("user-b", "project-b"))
    assert res.status_code == 200
    assert res.json()["id"] == "mix-b"


def test_cross_project_job_events_are_not_found(client):
    res = client.get(
        "/api/v1/jobs/job-b/events", headers=_bearer("user-a", "project-a")
    )
    assert res.status_code == 404


def test_unauthenticated_job_event_stream_is_rejected_when_enforced(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "auth_enforced", True)
    assert client.get("/api/v1/jobs/job-b/events").status_code == 401
    assert client.get("/api/v1/mixes/mix-b").status_code == 401


def test_open_mode_reads_default_project_without_token(client):
    res = client.get("/api/v1/mixes/mix-d")
    assert res.status_code == 200
    # ...but the foreign project stays invisible without its token.
    assert client.get("/api/v1/mixes/mix-b").status_code == 404


def test_invalid_bearer_token_is_rejected(client):
    res = client.get(
        "/api/v1/mixes/mix-b", headers={"Authorization": "Bearer not-a-token"}
    )
    assert res.status_code == 401


def test_token_for_unowned_project_is_rejected(client):
    res = client.get("/api/v1/mixes/mix-b", headers=_bearer("user-a", "project-b"))
    assert res.status_code == 401
