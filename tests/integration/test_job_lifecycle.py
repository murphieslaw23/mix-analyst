"""Integration coverage for durable job commands and worker claims."""

import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.session import Base
from api.app.models.identity import Project, User
from api.app.models.job import Job, JobAttempt, JobStatus
from api.app.models.media import MediaAsset, Mix
from api.app.models.outbox import OutboxMessage
from api.app.models.artifact import Artifact
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

    assert transition_job_and_attempt(db, job.id, principal.project_id, "worker-a", terminal_status, "worker failure") is False
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
    assert calls[0][0][0] == "tasks.run_master_mix"


def test_master_worker_records_immutable_stage_report(db, principal, mix, monkeypatch, tmp_path):
    """A claimed mastering job reaches success only after its worker report exists."""
    import worker.tasks as worker_tasks
    from tests.fixtures.synthetic_audio import generate_synthetic_audio

    source_key = "projects/project-a/artifacts/source/v1/" + "c" * 64
    source_path = tmp_path / source_key
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(generate_synthetic_audio(duration_sec=3.0))
    mix.media_asset.storage_path = source_key
    job = enqueue_job(
        db,
        principal,
        mix,
        JobCreateRequest(
            job_type="MASTERING",
            parameters={"target_lufs": -9.0, "true_peak_dbtp": -1.0, "algorithm_version": "v1"},
        ),
    )
    db.commit()

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(worker_tasks, "STORAGE_ROOT", str(tmp_path))
    monkeypatch.setattr(worker_tasks, "publish_event", lambda *_args, **_kwargs: None)

    result = worker_tasks.run_master_mix.run(job.id, principal.project_id)

    assert result["status"] == "ok"
    stored_job = db.get(Job, job.id)
    assert stored_job.status is JobStatus.SUCCEEDED
    stage = stored_job.stage_runs[0]
    report = json.loads(stage.stage_output)
    assert stage.status.value == "COMPLETED"
    assert report["artifact_key"].startswith("projects/project-a/artifacts/mastered/v1/")
    assert (tmp_path / report["artifact_key"]).is_file()


def test_analysis_worker_persists_owner_scoped_metadata_and_waveform_artifacts(db, principal, mix, monkeypatch, tmp_path):
    """The durable analysis command stores stage reports only after artifacts exist."""
    import worker.tasks as worker_tasks
    from tests.fixtures.synthetic_audio import generate_synthetic_audio

    source_key = "projects/project-a/artifacts/source/v1/" + "e" * 64
    source_path = tmp_path / source_key
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(generate_synthetic_audio(duration_sec=2.0, bpm=150.0))
    mix.media_asset.storage_path = source_key
    mix.media_asset.sha256_hash = "e" * 64
    mix.media_asset.file_size_bytes = source_path.stat().st_size
    mix.media_asset.mime_type = "audio/wav"
    job = enqueue_job(db, principal, mix, JobCreateRequest(job_type="ANALYSIS"))
    db.commit()

    class DeterministicOrchestrator:
        def __init__(self, *_args):
            pass

        def execute_pipeline(self, progress_callback):
            progress_callback(60.0, "Stub analysis")
            return {
                "primary_bpm": 150.0, "bpm_confidence": 1.0, "bpm_candidates": [],
                "detected_key": "A", "camelot_code": "11A", "key_confidence": 1.0,
                "integrated_lufs": -12.0, "loudness_range_lra": 4.0, "true_peak_db": -1.0,
                "spectral_summary": {}, "quality_findings": [], "track_segments": [], "transitions": [],
            }

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(worker_tasks, "STORAGE_ROOT", str(tmp_path))
    monkeypatch.setattr(worker_tasks, "publish_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker_tasks, "AudioAnalysisOrchestrator", DeterministicOrchestrator)

    assert worker_tasks.run_analysis_pipeline.run(job.id, principal.project_id)["status"] == "ok"
    artifacts = db.query(Artifact).filter(Artifact.mix_id == mix.id).all()
    by_role = {artifact.role: artifact for artifact in artifacts}
    assert {"source", "metadata", "waveform"} <= set(by_role)
    assert by_role["metadata"].key.startswith("projects/project-a/artifacts/metadata/v1/")
    assert by_role["waveform"].key.startswith("projects/project-a/artifacts/waveform/v1/")
    assert by_role["metadata"].report["suggested_download_name"].endswith(".wav")
    assert (tmp_path / by_role["metadata"].key).is_file()
    assert (tmp_path / by_role["waveform"].key).is_file()


def test_shared_source_artifacts_attach_to_each_mix_without_rewriting_object(db, principal, mix, monkeypatch, tmp_path):
    """Deduplicated bytes remain one object while each mix gets durable references."""
    import worker.tasks as worker_tasks
    from tests.fixtures.synthetic_audio import generate_synthetic_audio

    source_key = "projects/project-a/artifacts/source/v1/" + "f" * 64
    source_path = tmp_path / source_key
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(generate_synthetic_audio(duration_sec=2.0, bpm=150.0))
    mix.media_asset.storage_path = source_key
    mix.media_asset.sha256_hash = "f" * 64
    mix.media_asset.file_size_bytes = source_path.stat().st_size
    mix.media_asset.mime_type = "audio/wav"
    second_mix = Mix(id="mix-shared", project_id="project-a", title="Shared bytes", media_asset=mix.media_asset, status="ready")
    db.add(second_mix)
    first_job = enqueue_job(db, principal, mix, JobCreateRequest(job_type="ANALYSIS"))
    second_job = enqueue_job(db, principal, second_mix, JobCreateRequest(job_type="ANALYSIS"))
    db.commit()

    class DeterministicOrchestrator:
        def __init__(self, *_args):
            pass

        def execute_pipeline(self, progress_callback):
            progress_callback(60.0, "Stub analysis")
            return {
                "primary_bpm": 150.0, "bpm_confidence": 1.0, "bpm_candidates": [],
                "detected_key": "A", "camelot_code": "11A", "key_confidence": 1.0,
                "integrated_lufs": -12.0, "loudness_range_lra": 4.0, "true_peak_db": -1.0,
                "spectral_summary": {}, "quality_findings": [], "track_segments": [], "transitions": [],
            }

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(worker_tasks, "STORAGE_ROOT", str(tmp_path))
    monkeypatch.setattr(worker_tasks, "publish_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker_tasks, "AudioAnalysisOrchestrator", DeterministicOrchestrator)

    assert worker_tasks.run_analysis_pipeline.run(first_job.id, principal.project_id)["status"] == "ok"
    assert worker_tasks.run_analysis_pipeline.run(second_job.id, principal.project_id)["status"] == "ok"

    first_artifacts = {item.role: item for item in db.query(Artifact).filter(Artifact.mix_id == mix.id)}
    second_artifacts = {item.role: item for item in db.query(Artifact).filter(Artifact.mix_id == second_mix.id)}
    assert set(first_artifacts) == set(second_artifacts) == {"source", "metadata", "waveform"}
    assert first_artifacts["waveform"].key == second_artifacts["waveform"].key
    assert first_artifacts["metadata"].key == second_artifacts["metadata"].key
    assert (tmp_path / first_artifacts["waveform"].key).is_file()


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
