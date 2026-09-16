"""Shared SQLite seeding helpers for pipeline tests (no Postgres/Redis needed)."""

import io
from datetime import datetime, timezone
from pathlib import Path

import soundfile as sf
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import registers every model on Base.metadata (intentional re-export).
from api.app import models as models  # noqa: PLC0414
from api.app.db.session import Base
from api.app.models.job import Job, JobAttempt, JobStatus, JobType
from api.app.models.media import MediaAsset, Mix
from api.app.models.stems import StemJob


def make_session(tmp_path: Path):
    """Create a fresh SQLite database with the full application schema."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed_mix(
    db,
    storage_root: Path,
    wav_bytes: bytes,
    *,
    mix_id: str = "m1",
    asset_id: str = "a1",
    filename: str = "set.wav",
) -> str:
    """Write an audio file into storage and register MediaAsset + Mix rows."""
    rel_path = f"assets/audio/{asset_id}.wav"
    abs_path = storage_root / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(wav_bytes)

    info = sf.info(io.BytesIO(wav_bytes))
    db.add(
        MediaAsset(
            id=asset_id,
            original_filename=filename,
            storage_path=rel_path,
            file_size_bytes=len(wav_bytes),
            sha256_hash="0" * 64,
            duration_seconds=float(info.duration),
            sample_rate=int(info.samplerate),
            channels=int(info.channels),
            codec="pcm",
        )
    )
    db.add(
        Mix(
            id=mix_id,
            title="Test Set",
            artist="Tester",
            media_asset_id=asset_id,
            status="ready",
        )
    )
    db.commit()
    return mix_id


def seed_job(db, job_id: str, mix_id: str, job_type: JobType = JobType.ANALYSIS) -> str:
    """Insert a QUEUED generic job + first attempt."""
    db.add(
        Job(
            id=job_id,
            mix_id=mix_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            progress_percent=0.0,
            current_stage="Queued",
        )
    )
    db.add(
        JobAttempt(
            id=f"{job_id}-att1",
            job_id=job_id,
            attempt_number=1,
            status=JobStatus.QUEUED,
        )
    )
    db.commit()
    return job_id


def seed_completed_stems(
    db, storage_root: Path, mix_id: str, kick_wav: bytes, bass_wav: bytes
) -> str:
    """Write drums/bass stem files and register a completed StemJob row."""
    stem_dir = storage_root / "assets" / "derived" / "stems" / mix_id
    stem_dir.mkdir(parents=True, exist_ok=True)
    (stem_dir / "drums.wav").write_bytes(kick_wav)
    (stem_dir / "bass.wav").write_bytes(bass_wav)
    stem_id = f"sj-{mix_id}"
    db.add(
        StemJob(
            id=stem_id,
            media_id=mix_id,
            model_name="test",
            status="completed",
            drums_path=f"assets/derived/stems/{mix_id}/drums.wav",
            bass_path=f"assets/derived/stems/{mix_id}/bass.wav",
            completed_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return stem_id
