"""Mastering trigger under enforced foreign keys (production parity).

SQLite ignores FK constraints by default, which hid the missing
mastering_presets seed (500 on Postgres). These tests run with
PRAGMA foreign_keys=ON so phantom references fail here first.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.app.main as main_mod
from api.app import models as models  # noqa: PLC0414  (registers metadata)
from api.app.db.session import Base, get_db
from api.app.main import app
from api.app.models.identity import Project, User
from api.app.models.mastering import MasteringPreset
from api.app.models.media import MediaAsset, Mix


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enforce_fk(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_factory()
    db.add(User(id="default-user"))
    db.add(Project(id="default-project", owner_id="default-user"))
    db.commit()
    db.add(
        MediaAsset(
            id="a1",
            project_id="default-project",
            original_filename="set.wav",
            storage_path="assets/audio/a1.wav",
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
            id="m1",
            title="T",
            project_id="default-project",
            media_asset_id="a1",
            status="ready",
        )
    )
    db.commit()
    db.close()

    monkeypatch.setattr(main_mod, "init_db", lambda: None)
    app.dependency_overrides[get_db] = lambda: session_factory()

    def fake_send_task(*args, **kwargs):
        result = SimpleNamespace()
        result.id = "celery-fake-id"
        return result

    # enqueue_pipeline_job dispatches through its own module-global client.
    import api.app.services.pipeline_jobs as pipeline_jobs_mod

    monkeypatch.setattr(
        pipeline_jobs_mod, "celery_client", SimpleNamespace(send_task=fake_send_task)
    )
    yield TestClient(app, raise_server_exceptions=False), session_factory
    app.dependency_overrides.clear()


def test_mastering_trigger_succeeds_with_enforced_foreign_keys(client):
    http, _ = client
    res = http.post("/api/v1/mixes/m1/master", json={"preset_id": "club_broadcast"})
    assert res.status_code == 202, res.text
    assert res.json()["preset_name"] == "Club Broadcast"


def test_builtin_presets_seeded_for_trigger(client):
    http, factory = client
    http.post("/api/v1/mixes/m1/master", json={"preset_id": "club_broadcast"})
    db = factory()
    try:
        presets = db.query(MasteringPreset).all()
        assert {p.id for p in presets} >= {
            "sound_system_heavy",
            "club_broadcast",
            "vinyl_premaster",
        }
        assert all(p.is_builtin for p in presets)
    finally:
        db.close()
