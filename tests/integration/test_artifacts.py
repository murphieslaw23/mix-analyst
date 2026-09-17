"""Immutable artifact records: deterministic identity, scoped reads."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.app.main as main_mod
from api.app import models as models  # noqa: PLC0414  (registers metadata)
from api.app.db.session import Base, get_db
from api.app.main import app
from api.app.models.artifact import Artifact
from api.app.models.media import MediaAsset, Mix
from api.app.services.artifacts import artifact_key, register_artifact
from tests.helpers.pipeline_seed import make_session


def test_artifact_key_is_stable_for_source_and_algorithm():
    first = artifact_key("abc123", "master", "twopass-mastering/1.0.0")
    second = artifact_key("abc123", "master", "twopass-mastering/1.0.0")
    assert first == second
    assert first.startswith("artifacts/master/twopass-mastering/1.0.0/abc123")
    assert artifact_key("abc123", "waveform", "1") != first


def test_register_reuses_identity_for_same_key(tmp_path):
    db = make_session(tmp_path)
    kwargs = {
        "project_id": "default-project",
        "mix_id": None,
        "role": "master",
        "key": "artifacts/master/v1/abc123",
        "sha256": "0" * 64,
        "algorithm_version": "v1",
        "media_type": "audio/wav",
        "byte_length": 128,
    }
    first = register_artifact(db, **kwargs)
    second = register_artifact(db, **kwargs)
    assert first.id == second.id
    assert db.query(Artifact).count() == 1


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_factory()
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
    register_artifact(
        db,
        project_id="default-project",
        mix_id="m1",
        role="master",
        key="assets/derived/m1_master_x.wav",
        sha256="1" * 64,
        algorithm_version="twopass-mastering/1.0.0",
        media_type="audio/wav",
        byte_length=1024,
    )
    db.close()

    monkeypatch.setattr(main_mod, "init_db", lambda: None)
    app.dependency_overrides[get_db] = lambda: session_factory()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_artifacts_listed_for_owned_mix(client):
    res = client.get("/api/v1/mixes/m1/artifacts")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["role"] == "master"
    assert items[0]["algorithm_version"] == "twopass-mastering/1.0.0"


def test_artifacts_hidden_for_foreign_mix(client):
    assert client.get("/api/v1/mixes/does-not-exist/artifacts").status_code == 404
