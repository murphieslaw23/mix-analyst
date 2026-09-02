"""Integration coverage for durable, project-scoped job event streams."""

import base64
import asyncio
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.session import Base, get_db
from api.app.main import app
from api.app.models.identity import Project, User
from api.app.models.job import Job, JobAttempt, JobStatus, JobType
from api.app.models.media import MediaAsset, Mix


def _bearer_token(user_id: str, project_id: str) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=")
    claims = json.dumps({"sub": user_id, "project_id": project_id}, separators=(",", ":")).encode()
    payload = base64.urlsafe_b64encode(claims).rstrip(b"=")
    signature = hmac.new(b"development-only-secret-change-me-32", header + b"." + payload, hashlib.sha256).digest()
    return b".".join((header, payload, base64.urlsafe_b64encode(signature).rstrip(b"="))).decode()


@pytest.fixture
def event_client():
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
                MediaAsset(
                    id="media-a",
                    project_id="project-a",
                    original_filename="mix.wav",
                    storage_path="projects/project-a/mix.wav",
                    file_size_bytes=1,
                    sha256_hash="a" * 64,
                    duration_seconds=1.0,
                    sample_rate=44100,
                    channels=2,
                    codec="pcm_s16le",
                ),
            ]
        )
        db.add(Mix(id="mix-a", project_id="project-a", media_asset_id="media-a", title="Owned mix", status="ready"))
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
def token():
    return _bearer_token("user-a", "project-a")


@pytest.fixture
def job(event_client):
    _, session_factory = event_client
    db = session_factory()
    try:
        job = Job(
            id="job-a",
            project_id="project-a",
            mix_id="mix-a",
            job_type=JobType.ANALYSIS,
            status=JobStatus.RUNNING,
            progress_percent=50.0,
            current_stage="Analysis",
        )
        db.add(job)
        db.add(JobAttempt(id="attempt-a", job_id=job.id, attempt_number=1, status=JobStatus.RUNNING, worker_hostname="worker-a"))
        db.commit()
        return job
    finally:
        db.close()


@pytest.fixture
def job_with_succeeded_event(event_client, job):
    from api.app.services.job_events_store import record_job_event

    _, session_factory = event_client
    db = session_factory()
    try:
        persisted_job = db.get(Job, job.id)
        record_job_event(db, persisted_job, "update", {"job_id": job.id, "status": "QUEUED"})
        record_job_event(db, persisted_job, "update", {"job_id": job.id, "status": "RUNNING", "progress_percent": 50.0})
        persisted_job.status = JobStatus.SUCCEEDED
        record_job_event(
            db,
            persisted_job,
            "update",
            {"job_id": job.id, "status": "SUCCEEDED", "progress_percent": 100.0},
        )
        db.commit()
        return job
    finally:
        db.close()


def test_sse_replays_terminal_event_committed_before_subscription(event_client, token, job_with_succeeded_event):
    client, _ = event_client

    response = client.get(
        f"/api/v1/jobs/{job_with_succeeded_event.id}/events",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "id: 3" in response.text
    assert "SUCCEEDED" in response.text


def test_sse_last_event_id_replays_only_events_after_the_cursor(event_client, token, job_with_succeeded_event):
    client, _ = event_client

    response = client.get(
        f"/api/v1/jobs/{job_with_succeeded_event.id}/events",
        headers={"Authorization": f"Bearer {token}", "Last-Event-ID": "2"},
    )

    assert response.status_code == 200
    assert "id: 3" in response.text
    assert "id: 1" not in response.text
    assert "id: 2" not in response.text


def test_sse_replays_event_committed_during_redis_subscription(event_client, job, monkeypatch):
    """The DB read immediately after subscribe closes the replay/tail race."""
    from api.app.services import job_events
    from api.app.services.job_events_store import record_job_event

    _, session_factory = event_client
    seed_db = session_factory()
    try:
        persisted_job = seed_db.get(Job, job.id)
        record_job_event(seed_db, persisted_job, "update", {"job_id": job.id, "status": "RUNNING"})
        seed_db.commit()
    finally:
        seed_db.close()

    class FakePubSub:
        async def subscribe(self, _channel):
            writer_db = session_factory()
            try:
                persisted_job = writer_db.get(Job, job.id)
                persisted_job.status = JobStatus.SUCCEEDED
                record_job_event(writer_db, persisted_job, "update", {"job_id": job.id, "status": "SUCCEEDED"})
                writer_db.commit()
            finally:
                writer_db.close()

        async def get_message(self, **_kwargs):
            return None

        async def unsubscribe(self, _channel):
            return None

    class FakeRedis:
        def pubsub(self):
            return FakePubSub()

        async def aclose(self):
            return None

    monkeypatch.setattr(job_events.aioredis, "from_url", lambda *_args, **_kwargs: FakeRedis())

    async def collect_until_closed():
        stream_db = session_factory()
        try:
            stream = job_events.stream_job_events(stream_db, "project-a", job.id)
            events = [await anext(stream), await anext(stream)]
            with pytest.raises(StopAsyncIteration):
                await anext(stream)
            return events
        finally:
            stream_db.close()

    events = asyncio.run(collect_until_closed())
    assert ["id: 1" in event for event in events] == [True, False]
    assert "id: 2" in events[1]
    assert "SUCCEEDED" in events[1]


def test_event_stream_requires_ownership_before_replay(event_client, job_with_succeeded_event):
    client, _ = event_client
    foreign_token = _bearer_token("user-b", "project-b")

    response = client.get(
        f"/api/v1/jobs/{job_with_succeeded_event.id}/events",
        headers={"Authorization": f"Bearer {foreign_token}"},
    )

    assert response.status_code == 404


def test_recorded_events_are_monotonic_per_job(event_client, job):
    from api.app.models.job_event import JobEvent
    from api.app.services.job_events_store import record_job_event

    _, session_factory = event_client
    db = session_factory()
    try:
        persisted_job = db.get(Job, job.id)
        first = record_job_event(db, persisted_job, "update", {"status": "RUNNING"})
        second = record_job_event(db, persisted_job, "update", {"status": "RUNNING", "progress_percent": 75.0})
        db.commit()

        assert (first.sequence, second.sequence) == (1, 2)
        assert [event.sequence for event in db.scalars(select(JobEvent).where(JobEvent.job_id == job.id).order_by(JobEvent.sequence))] == [1, 2]
    finally:
        db.close()


def test_cancelled_job_cannot_be_overwritten_by_late_worker(event_client, job):
    from api.app.models.job_event import JobEvent
    from api.app.services.job_events_store import complete_job_attempt, request_cancellation

    _, session_factory = event_client
    db = session_factory()
    try:
        cancelled_job = request_cancellation(db, db.get(Job, job.id))
        db.commit()

        assert complete_job_attempt(db, cancelled_job.id, "project-a", "worker-a") is False
        assert db.get(Job, job.id).status is JobStatus.CANCELLED
        cancellation_event = db.scalar(select(JobEvent).where(JobEvent.job_id == job.id))
        assert cancellation_event.sequence == 1
        assert cancellation_event.payload["status"] == "CANCELLED"
    finally:
        db.close()


def test_completion_requires_owned_claimed_attempt_and_records_terminal_event(event_client, job):
    from api.app.models.job_event import JobEvent
    from api.app.services.job_events_store import complete_job_attempt

    _, session_factory = event_client
    db = session_factory()
    try:
        assert complete_job_attempt(db, job.id, "project-b", "worker-a") is False
        assert complete_job_attempt(db, job.id, "project-a", "worker-b") is False
        assert db.get(Job, job.id).status is JobStatus.RUNNING
        assert db.scalars(select(JobEvent).where(JobEvent.job_id == job.id)).all() == []

        assert complete_job_attempt(db, job.id, "project-a", "worker-a") is True
        db.commit()

        completed_job = db.get(Job, job.id)
        completed_attempt = db.scalar(select(JobAttempt).where(JobAttempt.job_id == job.id))
        completion_event = db.scalar(
            select(JobEvent).where(JobEvent.job_id == job.id, JobEvent.project_id == "project-a")
        )
        assert completed_job.status is JobStatus.SUCCEEDED
        assert completed_attempt.status is JobStatus.SUCCEEDED
        assert completion_event.sequence == 1
        assert completion_event.payload["status"] == "SUCCEEDED"
    finally:
        db.close()
