"""Integration coverage for durable job commands and worker claims."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.session import Base
from api.app.models.identity import Project, User
from api.app.models.job import Job, JobAttempt, JobStatus
from api.app.models.media import MediaAsset, Mix
from api.app.models.outbox import OutboxMessage
from api.app.schemas.auth import CurrentPrincipal
from api.app.schemas.job import JobCreateRequest
from api.app.services.job_commands import claim_job_attempt, enqueue_job


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = session_factory()
    try:
        session.add_all([User(id="user-a"), Project(id="project-a", owner_id="user-a")])
        media = MediaAsset(
            id="media-a",
            project_id="project-a",
            original_filename="mix.wav",
            storage_path="projects/project-a/artifacts/source/v1/abc",
            file_size_bytes=1,
            sha256_hash="a" * 64,
            duration_seconds=1.0,
            sample_rate=44100,
            channels=2,
            codec="pcm_s16le",
        )
        session.add(Mix(id="mix-a", project_id="project-a", title="Owned mix", media_asset=media, status="ready"))
        session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def principal():
    return CurrentPrincipal(user_id="user-a", project_id="project-a")


@pytest.fixture
def mix(db):
    return db.get(Mix, "mix-a")


def test_create_job_persists_outbox_before_broker_publish(db, principal, mix):
    job = enqueue_job(db, principal, mix, JobCreateRequest(job_type="ANALYSIS"))

    outbox = db.scalar(select(OutboxMessage).where(OutboxMessage.aggregate_id == job.id))
    assert outbox is not None
    assert outbox.kind == "job.dispatch"
    assert outbox.project_id == principal.project_id
    assert outbox.payload["job_id"] == job.id
    assert outbox.payload["project_id"] == principal.project_id
    assert outbox.payload["queue"] == "analysis-cpu"
    assert job.status is JobStatus.QUEUED


def test_only_one_worker_claims_queued_attempt(db, principal, mix):
    job = enqueue_job(db, principal, mix, JobCreateRequest(job_type="ANALYSIS"))
    db.commit()

    assert claim_job_attempt(db, job.id, "worker-a", principal.project_id) is not None
    assert claim_job_attempt(db, job.id, "worker-b", principal.project_id) is None
    assert db.get(Job, job.id).status is JobStatus.RUNNING


def test_claim_does_not_replace_cancelled_job(db, principal, mix):
    job = enqueue_job(db, principal, mix, JobCreateRequest(job_type="ANALYSIS"))
    db.commit()
    job.status = JobStatus.CANCELLED
    db.commit()

    assert claim_job_attempt(db, job.id, "worker-a", principal.project_id) is None
    assert db.get(Job, job.id).status is JobStatus.CANCELLED


def test_enqueue_job_rejects_mix_from_another_project(db, principal):
    foreign_mix = Mix(id="mix-b", project_id="project-b", title="Foreign mix", media_asset_id="media-b", status="ready")

    with pytest.raises(PermissionError, match="current project"):
        enqueue_job(db, principal, foreign_mix, JobCreateRequest(job_type="ANALYSIS"))


def test_worker_scope_and_cancellation_checks_are_authoritative(db, principal, mix):
    from worker.tasks import JobStopped, require_running_job

    job = enqueue_job(db, principal, mix, JobCreateRequest(job_type="ANALYSIS"))
    db.commit()
    assert claim_job_attempt(db, job.id, "worker-a", principal.project_id) is not None
    db.commit()

    require_running_job(db, job.id, principal.project_id)
    with pytest.raises(JobStopped):
        require_running_job(db, job.id, "project-b")

    job.status = JobStatus.CANCELLED
    db.commit()
    with pytest.raises(JobStopped):
        require_running_job(db, job.id, principal.project_id)


def test_worker_stops_before_orchestration_when_cancelled_after_claim(db, principal, mix, monkeypatch):
    import worker.tasks as worker_tasks

    job = enqueue_job(db, principal, mix, JobCreateRequest(job_type="ANALYSIS"))
    db.commit()
    job_id = job.id
    real_claim = worker_tasks.claim_job_attempt

    def claim_then_cancel(session, job_id, worker_name, project_id):
        attempt = real_claim(session, job_id, worker_name, project_id)
        session.get(Job, job_id).status = JobStatus.CANCELLED
        return attempt

    class UnexpectedOrchestrator:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("cancelled job entered audio orchestration")

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(worker_tasks, "claim_job_attempt", claim_then_cancel)
    monkeypatch.setattr(worker_tasks, "AudioAnalysisOrchestrator", UnexpectedOrchestrator)

    assert worker_tasks.run_analysis_pipeline.run(job_id, principal.project_id) == {
        "status": "cancelled",
        "job_id": job_id,
    }


@pytest.mark.parametrize("terminal_status", [JobStatus.SUCCEEDED, JobStatus.FAILED])
def test_terminal_transition_leaves_attempt_running_when_cancellation_wins_race(
    db, principal, mix, terminal_status
):
    from worker.tasks import transition_job_and_attempt

    job = enqueue_job(db, principal, mix, JobCreateRequest(job_type="ANALYSIS"))
    db.commit()
    assert claim_job_attempt(db, job.id, "worker-a", principal.project_id) is not None
    db.commit()
    job.status = JobStatus.CANCELLED
    db.commit()

    assert transition_job_and_attempt(db, job.id, principal.project_id, terminal_status, "worker failure") is False
    attempt = db.scalar(select(JobAttempt).where(JobAttempt.job_id == job.id))
    assert attempt.status is JobStatus.RUNNING


def test_dispatch_failure_leaves_outbox_retryable(db, principal, mix):
    from worker.outbox_dispatcher import dispatch_pending_messages

    enqueue_job(db, principal, mix, JobCreateRequest(job_type="ANALYSIS"))
    db.commit()

    class UnavailableBroker:
        def send_task(self, *_args, **_kwargs):
            raise ConnectionError("broker unavailable")

    assert dispatch_pending_messages(db, celery_client=UnavailableBroker()) == 0
    outbox = db.scalar(select(OutboxMessage))
    assert outbox.delivered_at is None
    assert outbox.delivery_attempts == 1
    assert "broker unavailable" in outbox.last_error


def test_dispatch_marks_outbox_delivered_only_after_broker_accepts(db, principal, mix):
    from worker.outbox_dispatcher import dispatch_pending_messages

    job = enqueue_job(db, principal, mix, JobCreateRequest(job_type="MASTERING"))
    db.commit()
    calls = []

    class AcceptedBroker:
        def send_task(self, *args, **kwargs):
            calls.append((args, kwargs))
            return type("Result", (), {"id": "broker-task-id"})()

    assert dispatch_pending_messages(db, celery_client=AcceptedBroker()) == 1
    outbox = db.scalar(select(OutboxMessage))
    assert outbox.delivered_at is not None
    assert outbox.delivery_attempts == 1
    assert db.get(Job, job.id).celery_task_id == "broker-task-id"
    assert calls[0][1]["args"] == [job.id, principal.project_id]
    assert calls[0][1]["queue"] == "dsp-heavy"


def test_worker_routes_are_explicit_and_loss_safe():
    from worker.celery_app import celery_app

    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert {"analysis-cpu", "dsp-heavy", "metadata-network", "exports"}.issubset(
        {queue.name for queue in celery_app.conf.task_queues}
    )


def test_transient_event_channels_are_project_namespaced():
    from api.app.services.job_events import job_event_channel

    assert job_event_channel("project-a", "job-a") == "project:project-a:job:job-a:events"
    assert job_event_channel("project-a", "job-a") != job_event_channel("project-b", "job-a")
