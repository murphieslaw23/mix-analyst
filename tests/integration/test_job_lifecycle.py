"""Durable job commands: outbox persistence, atomic claims, safe retries."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.app.api.v1.jobs as jobs_mod
import api.app.main as main_mod
from api.app import models as models  # noqa: PLC0414  (registers metadata)
from api.app.db.session import Base, get_db
from api.app.main import app
from api.app.models.job import Job, JobStatus, JobType
from api.app.models.media import MediaAsset, Mix
from api.app.models.outbox import OutboxMessage
from api.app.services.job_commands import (
    claim_queued_job,
    complete_job_attempt,
    enqueue_job,
)
from tests.helpers.pipeline_seed import make_session, seed_job
from worker.outbox_dispatcher import dispatch_pending


def _sender_ok(calls):
    def _send(task_name, args, task_id, queue):
        calls.append((task_name, args, task_id, queue))
        return f"broker-{task_id}"

    return _send


def _sender_down():
    def _send(task_name, args, task_id, queue):
        raise OSError("broker unreachable")

    return _send


def test_create_job_persists_outbox_before_broker_publish(tmp_path):
    """The dispatch command commits before any broker contact."""
    db = make_session(tmp_path)
    seen = {}

    def _send(task_name, args, task_id, queue):
        row = (
            db.query(OutboxMessage)
            .filter(OutboxMessage.aggregate_id == args[0])
            .first()
        )
        seen["outbox_committed"] = row is not None and row.delivered_at is None
        return "broker-1"

    job = enqueue_job(
        db,
        mix_id="m1",
        job_type=JobType.ANALYSIS,
        task_name="tasks.run_analysis_pipeline",
        task_args=lambda new_id: [new_id],
        queue="analysis",
        sender=_send,
    )
    assert seen["outbox_committed"] is True
    assert job.status == JobStatus.QUEUED
    assert job.celery_task_id == "broker-1"


def test_broker_failure_keeps_durable_queued_job(tmp_path):
    """A down broker must not lose the job: QUEUED + retryable outbox row."""
    db = make_session(tmp_path)
    job = enqueue_job(
        db,
        mix_id="m1",
        job_type=JobType.ANALYSIS,
        task_name="tasks.run_analysis_pipeline",
        task_args=["x"],
        queue="analysis",
        sender=_sender_down(),
    )
    assert job.status == JobStatus.QUEUED
    row = db.query(OutboxMessage).filter(OutboxMessage.aggregate_id == job.id).one()
    assert row.delivered_at is None
    assert row.delivery_attempts >= 1
    assert "unreachable" in (row.last_error or "")


def test_only_one_worker_claims_queued_attempt(tmp_path):
    db = make_session(tmp_path)
    seed_job(db, "job-1", "m1")
    assert claim_queued_job(db, "job-1", "worker-a") is True
    assert claim_queued_job(db, "job-1", "worker-b") is False
    assert db.query(Job).filter(Job.id == "job-1").one().status == JobStatus.RUNNING


def test_cancelled_job_cannot_be_overwritten_by_late_worker(tmp_path):
    db = make_session(tmp_path)
    seed_job(db, "job-1", "m1")
    db.query(Job).filter(Job.id == "job-1").update({Job.status: JobStatus.CANCELLED})
    db.commit()
    assert claim_queued_job(db, "job-1", "worker-a") is False
    assert complete_job_attempt(db, "job-1", ok=True) is False
    assert complete_job_attempt(db, "job-1", ok=False, error="late") is False
    assert db.query(Job).filter(Job.id == "job-1").one().status == JobStatus.CANCELLED


def test_dispatcher_delivers_pending_after_outage(tmp_path):
    db = make_session(tmp_path)
    job = enqueue_job(
        db,
        mix_id="m1",
        job_type=JobType.ANALYSIS,
        task_name="tasks.run_analysis_pipeline",
        task_args=["x"],
        queue="analysis",
        sender=_sender_down(),
    )
    calls: list = []
    delivered = dispatch_pending(db, _sender_ok(calls))
    assert delivered == 1
    assert calls and calls[0][1] == ["x"]
    db.refresh(job)
    assert job.celery_task_id == f"broker-job_{job.id}"
    row = db.query(OutboxMessage).filter(OutboxMessage.aggregate_id == job.id).one()
    assert row.delivered_at is not None


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
    db.commit()
    db.close()

    monkeypatch.setattr(main_mod, "init_db", lambda: None)
    app.dependency_overrides[get_db] = lambda: session_factory()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_route_returns_201_with_retryable_outbox_when_broker_down(client, monkeypatch):
    """POST /mixes/{id}/jobs survives a broker outage (durable QUEUED)."""

    def _boom(*args, **kwargs):
        raise OSError("broker unreachable")

    monkeypatch.setattr(jobs_mod, "celery_client", SimpleNamespace(send_task=_boom))
    res = client.post("/api/v1/mixes/m1/jobs", json={"job_type": "ANALYSIS"})
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "QUEUED"


def test_worker_claim_guard_rejects_cancelled_job(tmp_path):
    """The worker-side raw-SQL claim mirrors the ORM guard."""
    from worker.tasks import _pipeline_mark_running

    db = make_session(tmp_path)
    seed_job(db, "job-9", "m1")
    db.query(Job).filter(Job.id == "job-9").update({Job.status: JobStatus.CANCELLED})
    db.commit()
    assert _pipeline_mark_running(db, "job-9", "worker-a", "X") is False
    db.close()
