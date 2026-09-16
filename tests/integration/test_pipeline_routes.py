"""HTTP-level tests for pipeline triggers, auth, audio and upload hygiene."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api.app.api.deps as deps
import api.app.api.v1.mixes as mixes_mod
import api.app.api.v1.sidechain as sidechain_mod
import api.app.api.v1.mastering as mastering_mod
import api.app.api.v1.uploads as uploads_mod
import api.app.main as main_mod
import api.app.services.pipeline_jobs as pipeline_jobs
from api.app.db.session import get_db
from api.app.main import app
from tests.fixtures.synthetic_audio import generate_synthetic_audio
from tests.helpers.pipeline_seed import make_session, seed_completed_stems, seed_mix


class FakeCeleryResult:
    id = "celery-fake-id"


@pytest.fixture
def client(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    storage.mkdir()
    db = make_session(tmp_path)

    # No real Postgres on startup in tests.
    monkeypatch.setattr(main_mod, "init_db", lambda: None)
    app.dependency_overrides[get_db] = lambda: db

    # No real Redis/Celery: capture dispatches instead.
    sent = []

    def fake_send_task(*args, **kwargs):
        sent.append((args, kwargs))
        return FakeCeleryResult()

    monkeypatch.setattr(pipeline_jobs, "celery_client", SimpleNamespace(send_task=fake_send_task))

    # Point file-serving routes at tmp storage; auth open by default.
    storage_settings = SimpleNamespace(
        storage_root=str(storage),
        api_v1_prefix="/api/v1",
        max_upload_size_bytes=50 * 1024 * 1024,
        upload_expiry_hours=24,
    )
    monkeypatch.setattr(mixes_mod, "settings", storage_settings)
    monkeypatch.setattr(sidechain_mod, "app_settings", storage_settings)
    monkeypatch.setattr(mastering_mod, "app_settings", storage_settings)
    monkeypatch.setattr(uploads_mod, "settings", storage_settings)
    from api.app.services.storage import StorageService

    monkeypatch.setattr(uploads_mod, "storage", StorageService(str(storage)))
    monkeypatch.setattr(deps, "settings", SimpleNamespace(api_keys=set()))

    seed_mix(db, storage, generate_synthetic_audio(duration_sec=5.0, bpm=120.0))

    with TestClient(app) as test_client:
        yield SimpleNamespace(client=test_client, db=db, storage=storage, sent=sent)
    app.dependency_overrides.clear()


def test_mastering_trigger_enqueues_202(client):
    res = client.client.post("/api/v1/mixes/m1/master", json={"preset_id": "club_broadcast"})
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["status"] == "queued"
    assert body["preset_name"] == "Club Broadcast"
    dispatches = [kw for _, kw in client.sent if "run_mastering_pipeline" in str(kw.get("args", [])) or "run_mastering_pipeline" == kw.get("task", "")]
    # send_task called positionally: (task_name, args=..., ...)
    assert any(a and a[0] == "tasks.run_mastering_pipeline" for a, _ in client.sent)
    assert any(kw.get("queue") == "mastering" for _, kw in client.sent)


def test_mastering_trigger_rejects_unknown_preset(client):
    res = client.client.post("/api/v1/mixes/m1/master", json={"preset_id": "nope"})
    assert res.status_code == 400


def test_stems_trigger_enqueues_202(client):
    res = client.client.post("/api/v1/mixes/m1/stems", json={"model_name": "htdemucs"})
    assert res.status_code == 202, res.text
    assert res.json()["status"] == "queued"
    assert any(a and a[0] == "tasks.run_stem_separation" for a, _ in client.sent)
    assert any(kw.get("queue") == "stems" for _, kw in client.sent)


def test_sidechain_trigger_409_without_stems(client):
    res = client.client.post(
        "/api/v1/mastering/sidechain",
        json={"media_id": "m1", "threshold_db": -12.0, "max_ducking_db": 6.0},
    )
    assert res.status_code == 409


def test_sidechain_trigger_202_with_stems(client):
    kick = generate_synthetic_audio(duration_sec=5.0, bpm=120.0, freq_hz=55.0)
    bass = generate_synthetic_audio(duration_sec=5.0, bpm=120.0, freq_hz=110.0)
    seed_completed_stems(client.db, client.storage, "m1", kick, bass)

    res = client.client.post("/api/v1/mastering/sidechain", json={"media_id": "m1"})
    assert res.status_code == 202, res.text
    assert res.json()["status"] == "queued"
    assert any(a and a[0] == "tasks.run_sidechain" for a, _ in client.sent)

    report = client.client.get("/api/v1/mixes/m1/sidechain")
    assert report.status_code == 200
    assert report.json()["status"] == "queued"


def test_compositor_trigger_enqueues_render(client):
    res = client.client.post(
        "/api/v1/broadcast/render-stream",
        json={"media_id": "m1", "stream_title": "T", "artist_name": "A", "bpm": 130.0, "camelot_key": "8A"},
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["status"] == "rendering"
    assert "showfreqs" in body["filter_complex"]
    assert any(a and a[0] == "tasks.run_broadcast_render" for a, _ in client.sent)
    assert any(kw.get("queue") == "exports" for _, kw in client.sent)


def test_jobs_list_and_audio_and_mastered(client):
    client.client.post("/api/v1/mixes/m1/stems", json={})
    jobs = client.client.get("/api/v1/mixes/m1/jobs")
    assert jobs.status_code == 200
    assert len(jobs.json()) >= 1
    assert jobs.json()[0]["job_type"] == "STEM_SEPARATION"

    audio = client.client.get("/api/v1/mixes/m1/audio")
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/wav"

    assert client.client.get("/api/v1/mixes/nope/audio").status_code == 404
    assert client.client.get("/api/v1/mixes/m1/mastered").status_code == 404
    assert client.client.get("/api/v1/mixes/m1/sidechain").status_code == 404
    assert client.client.get("/api/v1/mixes/m1/mastering-report").status_code == 404


def test_mix_detail_shape(client):
    res = client.client.get("/api/v1/mixes/m1")
    assert res.status_code == 200
    body = res.json()
    assert body["audio_url"] == "/api/v1/mixes/m1/audio"
    assert body["duration_seconds"] > 0
    assert isinstance(body["tracks"], list)


def test_auth_locked_mode(client, monkeypatch):
    monkeypatch.setattr(deps, "settings", SimpleNamespace(api_keys={"s3cret"}))

    no_header = client.client.post("/api/v1/mixes/m1/stems", json={})
    assert no_header.status_code == 401

    wrong = client.client.post("/api/v1/mixes/m1/stems", json={}, headers={"X-API-Key": "wrong"})
    assert wrong.status_code == 401

    ok = client.client.post("/api/v1/mixes/m1/stems", json={}, headers={"X-API-Key": "s3cret"})
    assert ok.status_code == 202

    # Reads stay open.
    assert client.client.get("/api/v1/mixes/m1").status_code == 200
    assert client.client.get("/api/v1/mixes/m1/audio").status_code == 200


def test_upload_init_chunk_abort_flow(client):
    init = client.client.post(
        "/api/v1",
        json={"filename": "set.wav", "total_size_bytes": 8, "chunk_size": 8},
    )
    assert init.status_code == 201, init.text
    upload_id = init.json()["upload_id"]

    chunk = client.client.patch(
        f"/api/v1/{upload_id}",
        files={"file": ("chunk.bin", b"12345678")},
        data={"offset": "0"},
    )
    assert chunk.status_code == 200
    assert chunk.json()["bytes_received"] == 8

    abort = client.client.delete(f"/api/v1/{upload_id}")
    assert abort.status_code == 204

    status = client.client.get(f"/api/v1/{upload_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "ABORTED"
