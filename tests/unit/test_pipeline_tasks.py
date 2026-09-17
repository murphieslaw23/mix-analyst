"""Worker pipeline tasks against SQLite + tmp storage (no Postgres/Redis)."""

import importlib.util
import shutil
from types import SimpleNamespace

import pytest

from api.app.models.broadcast import BroadcastSync
from api.app.models.job import Job, JobStatus, JobType, StageRun
from api.app.models.mastering import MasteringJob
from api.app.models.sidechain import SidechainJob
from api.app.models.stems import StemJob
from tests.fixtures.synthetic_audio import generate_synthetic_audio
from tests.helpers.pipeline_seed import (
    make_session,
    seed_completed_stems,
    seed_job,
    seed_mix,
)
from worker import tasks
from worker.tasks import (
    run_broadcast_render,
    run_mastering_pipeline,
    run_sidechain,
    run_stem_separation,
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    storage = tmp_path / "storage"
    storage.mkdir()
    db = make_session(tmp_path)
    events = []
    monkeypatch.setattr(tasks, "STORAGE_ROOT", str(storage))
    monkeypatch.setattr(
        tasks, "publish_event", lambda job_id, payload: events.append(payload)
    )
    monkeypatch.setattr(tasks, "SessionLocal", sessionmaker(bind=db.get_bind()))
    return SimpleNamespace(db=db, storage=storage, events=events)


def _fresh(db, *models):
    db.expire_all()
    return [db.query(m).all() for m in models]


def test_run_mastering_pipeline_renders_real_master(env):
    wav = generate_synthetic_audio(duration_sec=10.0, bpm=120.0)
    seed_mix(env.db, env.storage, wav)
    env.db.add(
        MasteringJob(
            id="mj1", media_id="m1", preset_id="club_broadcast", status="queued"
        )
    )
    seed_job(env.db, "j1", "m1", JobType.MASTERING)
    env.db.commit()

    result = run_mastering_pipeline("j1", "mj1")

    assert result["status"] == "ok"
    assert result["compliance_passed"] is True
    env.db.expire_all()
    row = env.db.query(MasteringJob).filter_by(id="mj1").one()
    assert row.status == "completed"
    assert row.output_lufs == pytest.approx(-14.0, abs=1.0)
    assert row.input_lufs is not None and row.input_lufs < 0.0
    assert (env.storage / row.output_storage_path).is_file()
    assert env.db.query(Job).filter_by(id="j1").one().status == JobStatus.SUCCEEDED
    stages = env.db.query(StageRun).filter_by(job_id="j1").all()
    assert len(stages) >= 3
    assert {s.status for s in stages} == {"COMPLETED"}
    assert env.events and env.events[-1]["status"] == "SUCCEEDED"


def test_run_mastering_pipeline_missing_audio_fails_job(env):
    seed_mix(env.db, env.storage, generate_synthetic_audio(duration_sec=5.0))
    (env.storage / "assets" / "audio" / "a1.wav").unlink()  # simulate lost file
    env.db.add(
        MasteringJob(
            id="mj9", media_id="m1", preset_id="club_broadcast", status="queued"
        )
    )
    seed_job(env.db, "j9", "m1", JobType.MASTERING)
    env.db.commit()

    with pytest.raises(FileNotFoundError):
        run_mastering_pipeline("j9", "mj9")

    env.db.expire_all()
    assert env.db.query(MasteringJob).filter_by(id="mj9").one().status == "failed"
    assert env.db.query(Job).filter_by(id="j9").one().status == JobStatus.FAILED
    assert env.events and env.events[-1]["status"] == "FAILED"


def test_run_sidechain_on_real_stems(env):
    kick = generate_synthetic_audio(duration_sec=10.0, bpm=120.0, freq_hz=55.0)
    bass = generate_synthetic_audio(duration_sec=10.0, bpm=120.0, freq_hz=110.0)
    seed_mix(env.db, env.storage, kick)
    seed_completed_stems(env.db, env.storage, "m1", kick, bass)
    env.db.add(
        SidechainJob(
            id="sc1",
            media_id="m1",
            status="queued",
            threshold_db=-12.0,
            max_ducking_db=6.0,
        )
    )
    seed_job(env.db, "j2", "m1", JobType.SIDECHAIN)
    env.db.commit()

    result = run_sidechain("j2", "sc1")

    assert result["status"] == "ok"
    env.db.expire_all()
    row = env.db.query(SidechainJob).filter_by(id="sc1").one()
    assert row.status == "completed"
    assert row.phase_correlation is not None
    assert row.low_end_clarity_score is not None
    assert env.db.query(Job).filter_by(id="j2").one().status == JobStatus.SUCCEEDED


def test_run_sidechain_without_stems_fails_clearly(env):
    seed_mix(env.db, env.storage, generate_synthetic_audio(duration_sec=5.0))
    env.db.add(SidechainJob(id="sc9", media_id="m1", status="queued"))
    seed_job(env.db, "j8", "m1", JobType.SIDECHAIN)
    env.db.commit()

    with pytest.raises(RuntimeError, match="stem separation"):
        run_sidechain("j8", "sc9")

    env.db.expire_all()
    assert env.db.query(SidechainJob).filter_by(id="sc9").one().status == "failed"


def test_run_stem_separation_without_demucs_fails_actionably(env):
    if (
        importlib.util.find_spec("demucs") is not None
        or shutil.which("demucs") is not None
    ):
        pytest.skip("demucs is installed; nothing to prove here")
    seed_mix(env.db, env.storage, generate_synthetic_audio(duration_sec=5.0))
    env.db.add(StemJob(id="sj9", media_id="m1", model_name="htdemucs", status="queued"))
    seed_job(env.db, "j7", "m1", JobType.STEM_SEPARATION)
    env.db.commit()

    with pytest.raises(RuntimeError, match="Demucs is not installed"):
        run_stem_separation("j7", "sj9")

    env.db.expire_all()
    assert env.db.query(StemJob).filter_by(id="sj9").one().status == "failed"
    assert env.db.query(Job).filter_by(id="j7").one().status == JobStatus.FAILED


def test_run_broadcast_render_produces_mp4(env):
    wav = generate_synthetic_audio(duration_sec=3.0, bpm=130.0)
    seed_mix(env.db, env.storage, wav)
    seed_job(env.db, "j4", "m1", JobType.BROADCAST_RENDER)
    env.db.commit()

    result = run_broadcast_render(
        "j4",
        "m1",
        {
            "stream_title": "Test",
            "artist_name": "Tester",
            "bpm": 130.0,
            "camelot_key": "8A",
        },
    )

    assert result["status"] == "ok"
    assert (env.storage / result["output_path"]).is_file()
    env.db.expire_all()
    sync = env.db.query(BroadcastSync).filter_by(media_id="m1").one()
    assert sync.status == "rendered"
    assert env.db.query(Job).filter_by(id="j4").one().status == JobStatus.SUCCEEDED


def test_mastering_registers_immutable_artifact(env):
    """A completed master leaves exactly one content-addressed artifact row."""
    from api.app.models.artifact import Artifact

    wav = generate_synthetic_audio(duration_sec=10.0, bpm=120.0)
    seed_mix(env.db, env.storage, wav)
    env.db.add(
        MasteringJob(
            id="mjA", media_id="m1", preset_id="club_broadcast", status="queued"
        )
    )
    seed_job(env.db, "jA", "m1", JobType.MASTERING)
    env.db.commit()

    result = run_mastering_pipeline("jA", "mjA")
    assert result["status"] == "ok"

    env.db.expire_all()
    rows = env.db.query(Artifact).filter_by(mix_id="m1", role="master").all()
    assert len(rows) == 1
    assert rows[0].key.endswith("_master_club_broadcast.wav")
    assert len(rows[0].sha256) == 64
