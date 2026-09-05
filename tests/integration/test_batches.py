"""Integration coverage for durable, owner-scoped batch job aggregation."""

import base64
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
from api.app.models.batch import Batch
from api.app.models.identity import Project, User
from api.app.models.job import Job, JobAttempt, JobStatus
from api.app.models.media import MediaAsset, Mix
from api.app.models.outbox import OutboxMessage
from api.app.services.job_commands import claim_job_attempt, enqueue_retry
from api.app.services.batches import advance_batch_after_terminal_job


def _bearer_token(user_id: str, project_id: str) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=")
    claims = json.dumps({"sub": user_id, "project_id": project_id}, separators=(",", ":")).encode()
    payload = base64.urlsafe_b64encode(claims).rstrip(b"=")
    signature = hmac.new(b"development-only-secret-change-me-32", header + b"." + payload, hashlib.sha256).digest()
    return b".".join((header, payload, base64.urlsafe_b64encode(signature).rstrip(b"="))).decode()


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    db = session_factory()
    try:
        db.add_all([
            User(id="user-a"), User(id="user-b"),
            Project(id="project-a", owner_id="user-a"), Project(id="project-b", owner_id="user-b"),
        ])
        for mix_id, project_id in (("mix-a1", "project-a"), ("mix-a2", "project-a"), ("mix-b", "project-b")):
            media = MediaAsset(
                id=f"media-{mix_id}", project_id=project_id, original_filename=f"{mix_id}.wav",
                storage_path=f"projects/{project_id}/artifacts/source/v1/{mix_id}", file_size_bytes=1,
                sha256_hash=(mix_id[-1] * 64), duration_seconds=1.0, sample_rate=44100, channels=2, codec="pcm_s16le",
            )
            db.add(Mix(id=mix_id, project_id=project_id, title=mix_id, media_asset=media, status="ready"))
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
def other_token():
    return _bearer_token("user-b", "project-b")


@pytest.fixture
def owned_mix_ids():
    return ["mix-a1", "mix-a2"]


def _create_batch(client, token, mix_ids, max_parallelism=2):
    response = client.post(
        "/api/v1/batches",
        headers={"Authorization": f"Bearer {token}"},
        json={"mix_ids": mix_ids, "preset": {"target_lufs": -9.0}, "max_parallelism": max_parallelism},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_batch_reports_partial_failure_without_losing_successes(client, token, owned_mix_ids):
    test_client, session_factory = client
    batch = _create_batch(test_client, token, owned_mix_ids)
    assert batch["total_count"] == 2
    assert len(batch["items"]) == 2

    db = session_factory()
    try:
        jobs = db.scalars(select(Job).where(Job.batch_id == batch["id"]).order_by(Job.mix_id)).all()
        messages = db.scalars(select(OutboxMessage).where(OutboxMessage.aggregate_id.in_([job.id for job in jobs]))).all()
        assert len(messages) == 2
        assert {message.payload["job_id"] for message in messages} == {job.id for job in jobs}
        assert all(message.kind == "job.dispatch" for message in messages)
        jobs[0].status = JobStatus.SUCCEEDED
        jobs[1].status = JobStatus.FAILED
        db.commit()
    finally:
        db.close()

    response = test_client.get(f"/api/v1/batches/{batch['id']}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PARTIAL_FAILED"
    assert body["completed_count"] == 1
    assert body["failed_count"] == 1
    assert {item["status"] for item in body["items"]} == {"SUCCEEDED", "FAILED"}


def test_batch_retry_requeues_only_selected_failed_children(client, token, owned_mix_ids):
    test_client, session_factory = client
    batch = _create_batch(test_client, token, owned_mix_ids)
    db = session_factory()
    try:
        jobs = db.scalars(select(Job).where(Job.batch_id == batch["id"]).order_by(Job.mix_id)).all()
        successful, failed = jobs
        successful.status = JobStatus.SUCCEEDED
        failed.status = JobStatus.FAILED
        db.commit()
        successful_id, failed_id = successful.id, failed.id
    finally:
        db.close()

    response = test_client.post(
        f"/api/v1/batches/{batch['id']}/retry",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_ids": [failed_id]},
    )
    assert response.status_code == 200, response.text

    repeated = test_client.post(
        f"/api/v1/batches/{batch['id']}/retry",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_ids": [failed_id]},
    )
    assert repeated.status_code == 400

    db = session_factory()
    try:
        assert db.get(Job, successful_id).status is JobStatus.SUCCEEDED
        assert db.get(Job, failed_id).status is JobStatus.QUEUED
        assert db.query(JobAttempt).filter(JobAttempt.job_id == failed_id).count() == 2
        assert db.query(OutboxMessage).filter(OutboxMessage.aggregate_id == failed_id).count() == 2
    finally:
        db.close()


def test_batch_aggregate_is_persisted_and_cross_project_access_is_denied(client, token, other_token, owned_mix_ids):
    test_client, session_factory = client
    batch = _create_batch(test_client, token, owned_mix_ids)
    db = session_factory()
    try:
        jobs = db.scalars(select(Job).where(Job.batch_id == batch["id"])).all()
        jobs[0].status = JobStatus.SUCCEEDED
        jobs[1].status = JobStatus.CANCELLED
        db.commit()
    finally:
        db.close()

    response = test_client.get(f"/api/v1/batches/{batch['id']}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["completed_count"] == 1
    assert response.json()["cancelled_count"] == 1

    db = session_factory()
    try:
        db.expire_all()
        persisted = db.get(Batch, batch["id"])
        assert persisted.completed_count == 1
        assert persisted.cancelled_count == 1
    finally:
        db.close()

    response = test_client.get(f"/api/v1/batches/{batch['id']}", headers={"Authorization": f"Bearer {other_token}"})
    assert response.status_code == 404
    response = test_client.post(
        "/api/v1/batches",
        headers={"Authorization": f"Bearer {token}"},
        json={"mix_ids": ["mix-a1", "mix-b"], "max_parallelism": 1},
    )
    assert response.status_code == 404


def test_batch_worker_claims_respect_persisted_parallelism(client, token, owned_mix_ids):
    test_client, session_factory = client
    batch = _create_batch(test_client, token, owned_mix_ids, max_parallelism=1)
    db = session_factory()
    try:
        jobs = db.scalars(select(Job).where(Job.batch_id == batch["id"]).order_by(Job.mix_id)).all()
        assert claim_job_attempt(db, jobs[0].id, "worker-a", "project-a") is not None
        db.commit()
        assert db.get(Batch, batch["id"]).status.value == "RUNNING"
        assert claim_job_attempt(db, jobs[1].id, "worker-b", "project-a") is None
        assert db.get(Job, jobs[1].id).status is JobStatus.QUEUED
    finally:
        db.close()


def test_stale_retry_caller_cannot_append_a_second_attempt_or_outbox_command(client, token, owned_mix_ids):
    test_client, session_factory = client
    batch = _create_batch(test_client, token, owned_mix_ids)
    seed = session_factory()
    try:
        failed = seed.scalars(select(Job).where(Job.batch_id == batch["id"]).order_by(Job.mix_id)).all()[0]
        failed.status = JobStatus.FAILED
        seed.commit()
        failed_id = failed.id
    finally:
        seed.close()

    stale_session = session_factory()
    winning_session = session_factory()
    try:
        stale_job = stale_session.get(Job, failed_id)
        winning_job = winning_session.get(Job, failed_id)
        assert enqueue_retry(winning_session, winning_job, terminal_statuses=(JobStatus.FAILED,)) is not None
        winning_session.commit()

        # This models a second retry request that read FAILED before the first
        # request committed. The conditional FAILED -> QUEUED update must win
        # before attempt/outbox creation, so it cannot create a duplicate.
        assert enqueue_retry(stale_session, stale_job, terminal_statuses=(JobStatus.FAILED,)) is None
        stale_session.rollback()
    finally:
        stale_session.close()
        winning_session.close()

    verify = session_factory()
    try:
        assert verify.query(JobAttempt).filter(JobAttempt.job_id == failed_id).count() == 2
        assert verify.query(OutboxMessage).filter(OutboxMessage.aggregate_id == failed_id).count() == 2
    finally:
        verify.close()


def test_terminal_batch_child_refreshes_parent_and_redelivers_one_waiting_child(client, token, owned_mix_ids):
    test_client, session_factory = client
    batch = _create_batch(test_client, token, owned_mix_ids, max_parallelism=1)
    db = session_factory()
    try:
        jobs = db.scalars(select(Job).where(Job.batch_id == batch["id"]).order_by(Job.mix_id)).all()
        assert claim_job_attempt(db, jobs[0].id, "worker-a", "project-a") is not None
        jobs[0].status = JobStatus.SUCCEEDED
        advance_batch_after_terminal_job(db, jobs[0].id, "project-a")
        db.commit()

        parent = db.get(Batch, batch["id"])
        assert parent.completed_count == 1
        assert parent.total_count == 2
        assert db.query(OutboxMessage).filter(OutboxMessage.aggregate_id == jobs[1].id).count() == 2
    finally:
        db.close()


def test_cancelling_running_batch_child_redelivers_one_waiting_child(client, token, owned_mix_ids):
    """Cancellation frees a persisted slot and must advance the waiting queue."""
    test_client, session_factory = client
    batch = _create_batch(test_client, token, owned_mix_ids, max_parallelism=1)
    db = session_factory()
    try:
        jobs = db.scalars(select(Job).where(Job.batch_id == batch["id"]).order_by(Job.mix_id)).all()
        running, waiting = jobs
        assert claim_job_attempt(db, running.id, "worker-a", "project-a") is not None
        db.commit()
        running_id = running.id
        waiting_id = waiting.id
        assert db.query(OutboxMessage).filter(OutboxMessage.aggregate_id == waiting_id).count() == 1
    finally:
        db.close()

    response = test_client.post(
        f"/api/v1/jobs/{running_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    db = session_factory()
    try:
        assert db.get(Job, running_id).status is JobStatus.CANCELLED
        assert db.query(OutboxMessage).filter(OutboxMessage.aggregate_id == waiting_id).count() == 2
    finally:
        db.close()
