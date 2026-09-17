"""Durable job events: ordered persistence, SSE replay, safe cancellation."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.app.main as main_mod
from api.app import models as models  # noqa: PLC0414  (registers metadata)
from api.app.db.session import Base, get_db
from api.app.main import app
from api.app.models.job import Job, JobStatus
from api.app.models.job_event import JobEvent
from api.app.models.media import MediaAsset, Mix
from api.app.services.job_events_store import get_events_since, record_job_event
from tests.helpers.pipeline_seed import seed_job


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_factory()
    db.add(
        MediaAsset(
            id="a1",
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
    db.add(Mix(id="m1", title="T", media_asset_id="a1", status="ready"))
    seed_job(db, "job-1", "m1")
    db.close()

    monkeypatch.setattr(main_mod, "init_db", lambda: None)
    app.dependency_overrides[get_db] = lambda: session_factory()
    yield TestClient(app, raise_server_exceptions=False), session_factory
    app.dependency_overrides.clear()


def _snapshot(status, seq_note=""):
    return {
        "job_id": "job-1",
        "status": status,
        "progress_percent": 100.0 if status == "SUCCEEDED" else 0.0,
        "current_stage": seq_note or status,
    }


def test_event_sequences_are_monotonic(client):
    _, factory = client
    db = factory()
    seqs = [
        record_job_event(db, "job-1", "started", _snapshot("RUNNING", "s")).sequence,
        record_job_event(db, "job-1", "stage", _snapshot("RUNNING", "s")).sequence,
        record_job_event(db, "job-1", "terminal", _snapshot("SUCCEEDED")).sequence,
    ]
    db.close()
    assert seqs == [1, 2, 3]


def test_sse_replays_terminal_event_committed_before_subscription(client):
    http, factory = client
    db = factory()
    record_job_event(db, "job-1", "started", _snapshot("RUNNING", "Init"))
    record_job_event(db, "job-1", "stage", _snapshot("RUNNING", "Mix"))
    record_job_event(db, "job-1", "terminal", _snapshot("SUCCEEDED"))
    db.close()

    res = http.get("/api/v1/jobs/job-1/events")
    assert res.status_code == 200
    assert "id: 3" in res.text
    assert "SUCCEEDED" in res.text
    assert "event: close" in res.text


def test_last_event_id_filters_replay(client):
    http, factory = client
    db = factory()
    record_job_event(db, "job-1", "started", _snapshot("RUNNING", "Init"))
    record_job_event(db, "job-1", "stage", _snapshot("RUNNING", "Mix"))
    record_job_event(db, "job-1", "terminal", _snapshot("SUCCEEDED"))
    db.close()

    res = http.get("/api/v1/jobs/job-1/events", headers={"Last-Event-ID": "2"})
    assert res.status_code == 200
    assert "id: 3" in res.text
    assert "id: 1\nevent" not in res.text
    assert "id: 2\nevent" not in res.text


def test_sse_returns_404_for_unknown_job(client):
    http, _ = client
    res = http.get("/api/v1/jobs/does-not-exist/events")
    assert res.status_code == 404


def test_cancel_records_exactly_one_terminal_event(client):
    http, factory = client
    first = http.post("/api/v1/jobs/job-1/cancel")
    assert first.status_code == 200
    assert first.json()["status"] == "CANCELLED"
    second = http.post("/api/v1/jobs/job-1/cancel")
    assert second.json()["status"] == "CANCELLED"

    db = factory()
    terminals = (
        db.query(JobEvent)
        .filter(JobEvent.job_id == "job-1", JobEvent.event_type == "terminal")
        .all()
    )
    db.close()
    assert len(terminals) == 1
    assert json.loads(terminals[0].payload)["status"] == "CANCELLED"


def test_worker_terminal_never_overwrites_cancel(tmp_path, monkeypatch):
    """A losing worker emits no event and no fan-out for a cancelled job."""
    from tests.helpers.pipeline_seed import make_session
    from worker import tasks as tasks_mod

    published: list = []
    monkeypatch.setattr(
        tasks_mod, "publish_event", lambda job_id, payload: published.append(payload)
    )
    db = make_session(tmp_path)
    seed_job(db, "job-9", "m1")
    db.query(Job).filter(Job.id == "job-9").update({Job.status: JobStatus.CANCELLED})
    db.commit()
    assert tasks_mod._pipeline_mark_finished(db, "job-9", True) is False
    assert db.query(Job).filter(Job.id == "job-9").one().status == JobStatus.CANCELLED
    assert db.query(JobEvent).filter(JobEvent.job_id == "job-9").count() == 0
    assert published == []
    assert get_events_since(db, "job-9") == []
    db.close()
