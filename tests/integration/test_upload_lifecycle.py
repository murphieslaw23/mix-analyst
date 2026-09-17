"""Bounded owned upload lifecycle (core plan Task 3)."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api.app.api.v1.uploads as uploads_mod
import api.app.main as main_mod
from api.app import models as models  # noqa: PLC0414  (registers metadata)
from api.app.db.session import get_db
from api.app.main import app
from api.app.models.media import UploadSession
from api.app.services.storage import StorageService
from tests.fixtures.synthetic_audio import generate_synthetic_audio
from tests.helpers.pipeline_seed import make_session


@pytest.fixture
def client(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    storage.mkdir()
    db = make_session(tmp_path)

    monkeypatch.setattr(main_mod, "init_db", lambda: None)
    app.dependency_overrides[get_db] = lambda: db

    storage_settings = SimpleNamespace(
        storage_root=str(storage),
        api_v1_prefix="/api/v1",
        max_upload_size_bytes=50 * 1024 * 1024,
        default_chunk_size_bytes=5 * 1024 * 1024,
        upload_expiry_hours=24,
    )
    monkeypatch.setattr(uploads_mod, "settings", storage_settings)
    monkeypatch.setattr(uploads_mod, "storage", StorageService(str(storage)))
    yield TestClient(app, raise_server_exceptions=False), db, storage
    app.dependency_overrides.clear()


def _init(client, total: int, filename: str = "set.wav") -> str:
    res = client.post(
        "/api/v1/uploads", json={"filename": filename, "total_size_bytes": total}
    )
    assert res.status_code == 201, res.text
    return res.json()["upload_id"]


def _patch(client, upload_id: str, data: bytes, offset: int):
    return client.patch(
        f"/api/v1/uploads/{upload_id}",
        files={"file": ("chunk.bin", data)},
        data={"offset": str(offset)},
    )


def test_chunk_larger_than_configured_limit_is_rejected(client):
    http, _, _ = client
    upload_id = _init(http, 10 * 1024 * 1024)
    res = _patch(http, upload_id, b"x" * (5 * 1024 * 1024 + 1), 0)
    assert res.status_code == 413


def test_stale_offset_returns_conflict(client):
    http, _, _ = client
    upload_id = _init(http, 1000)
    res = _patch(http, upload_id, b"x" * 10, 5)
    assert res.status_code == 409


def test_chunk_past_declared_total_is_rejected(client):
    http, _, _ = client
    upload_id = _init(http, 100)
    assert _patch(http, upload_id, b"x" * 100, 0).status_code == 200
    res = _patch(http, upload_id, b"x" * 10, 100)
    assert res.status_code == 400


def test_checksum_mismatch_fails_completion(client):
    http, _, _ = client
    wav = generate_synthetic_audio(duration_sec=2.0)
    upload_id = _init(http, len(wav))
    assert _patch(http, upload_id, wav, 0).status_code == 200
    res = http.post(
        f"/api/v1/uploads/{upload_id}/complete",
        json={"title": "T", "sha256_hash": "f" * 64},
    )
    assert res.status_code == 400
    assert "checksum" in res.json()["detail"].lower()


def test_garbage_audio_fails_probe_with_422(client):
    http, _, _ = client
    garbage = b"not-audio-at-all" * 64
    upload_id = _init(http, len(garbage), "evil.bin")
    assert _patch(http, upload_id, garbage, 0).status_code == 200
    res = http.post(f"/api/v1/uploads/{upload_id}/complete", json={})
    assert res.status_code == 422


def test_foreign_project_session_is_not_found(client):
    http, db, storage = client
    db.add(
        UploadSession(
            id="sess-foreign",
            project_id="project-b",
            filename="x.wav",
            total_size_bytes=10,
            bytes_received=0,
            chunk_size=1024,
            temp_path=str(storage / "quarantine" / "upload_sess-foreign.tmp"),
            status="PENDING",
        )
    )
    db.commit()
    assert http.get("/api/v1/uploads/sess-foreign").status_code == 404
    assert _patch(http, "sess-foreign", b"x", 0).status_code == 404


def test_complete_creates_owned_mix_and_asset(client):
    http, _db, _ = client
    wav = generate_synthetic_audio(duration_sec=2.0)
    upload_id = _init(http, len(wav))
    assert _patch(http, upload_id, wav, 0).status_code == 200
    res = http.post(f"/api/v1/uploads/{upload_id}/complete", json={"title": "Live"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["title"] == "Live"
    assert len(body["sha256_hash"]) == 64
    mix_id = body["mix_id"]
    got = http.get(f"/api/v1/mixes/{mix_id}")
    assert got.status_code == 200
