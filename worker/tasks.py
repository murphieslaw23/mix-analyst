import os
import json
import socket
import shutil
import subprocess
import sys
import importlib.util
import redis
import uuid
import numpy as np
import soundfile as sf
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import text
from .celery_app import celery_app
from .db import SessionLocal
from .analysis.orchestrator import AudioAnalysisOrchestrator
from .analysis.mastering_engine import DEFAULT_PRESETS
from .analysis.dynamic_sidechain import DynamicSidechainDSP
from .analysis.stem_separator import StemSeparatorEngine
from .analysis.loudness_analyzer import measure_program_loudness
from .broadcast.ffmpeg_compositor import FFmpegBroadcastCompositor

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STORAGE_ROOT = os.getenv("STORAGE_ROOT", "/data/storage")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def publish_event(job_id: str, payload: dict) -> None:
    """Publish a real-time job event to the Redis pub/sub channel."""
    try:
        channel = f"job:{job_id}:events"
        redis_client.publish(channel, json.dumps(payload))
    except Exception as e:
        print(f"Failed to publish Redis event: {e}")


@celery_app.task(bind=True, name="tasks.run_analysis_pipeline")
def run_analysis_pipeline(self, job_id: str):
    """
    Execute the real bounded-memory audio analysis, fingerprinting & transition detection pipeline.
    """
    db = SessionLocal()
    hostname = socket.gethostname()
    start_time = datetime.now(timezone.utc)

    try:
        # 1. Fetch Job and Mix details
        job_row = db.execute(
            text("""
                SELECT j.id, j.mix_id, m.media_asset_id, a.storage_path, a.duration_seconds
                FROM jobs j
                JOIN mixes m ON j.mix_id = m.id
                JOIN media_assets a ON m.media_asset_id = a.id
                WHERE j.id = :id
            """),
            {"id": job_id},
        ).fetchone()

        if not job_row:
            return {"status": "error", "message": f"Job {job_id} not found"}

        mix_id = job_row.mix_id
        media_asset_id = job_row.media_asset_id
        storage_rel_path = job_row.storage_path
        duration_seconds = float(job_row.duration_seconds)
        audio_abs_path = Path(STORAGE_ROOT) / storage_rel_path

        # Transition Job to RUNNING
        db.execute(
            text("UPDATE jobs SET status = 'RUNNING', started_at = :now, current_stage = 'Initializing' WHERE id = :id"),
            {"id": job_id, "now": start_time},
        )
        db.execute(
            text("UPDATE job_attempts SET status = 'RUNNING', worker_hostname = :host, started_at = :now WHERE job_id = :id AND status = 'QUEUED'"),
            {"id": job_id, "host": hostname, "now": start_time},
        )
        db.commit()

        def progress_tracker(pct: float, stage_name: str):
            db.execute(
                text("UPDATE jobs SET current_stage = :stage, progress_percent = :pct WHERE id = :id"),
                {"id": job_id, "stage": stage_name, "pct": pct},
            )
            db.commit()
            publish_event(job_id, {
                "job_id": job_id,
                "status": "RUNNING",
                "progress_percent": pct,
                "current_stage": stage_name,
            })

        # Run real orchestrator
        orchestrator = AudioAnalysisOrchestrator(audio_abs_path, duration_seconds)
        analysis_data = orchestrator.execute_pipeline(progress_callback=progress_tracker)

        # Persist AnalysisResult in DB
        analysis_id = f"analysis_{mix_id}"
        db.execute(
            text("""
                INSERT INTO analysis_results (
                    id, mix_id, media_asset_id, primary_bpm, bpm_confidence,
                    bpm_candidates, detected_key, camelot_code, key_confidence,
                    integrated_lufs, loudness_range_lra, true_peak_db,
                    spectral_summary, quality_findings, created_at
                ) VALUES (
                    :id, :mix_id, :asset_id, :bpm, :bpm_conf,
                    :candidates, :key, :camelot, :key_conf,
                    :lufs, :lra, :tp,
                    :spectral, :quality, :now
                )
                ON CONFLICT (mix_id) DO UPDATE SET
                    primary_bpm = EXCLUDED.primary_bpm,
                    bpm_confidence = EXCLUDED.bpm_confidence,
                    bpm_candidates = EXCLUDED.bpm_candidates,
                    detected_key = EXCLUDED.detected_key,
                    camelot_code = EXCLUDED.camelot_code,
                    key_confidence = EXCLUDED.key_confidence,
                    integrated_lufs = EXCLUDED.integrated_lufs,
                    loudness_range_lra = EXCLUDED.loudness_range_lra,
                    true_peak_db = EXCLUDED.true_peak_db,
                    spectral_summary = EXCLUDED.spectral_summary,
                    quality_findings = EXCLUDED.quality_findings
            """),
            {
                "id": analysis_id,
                "mix_id": mix_id,
                "asset_id": media_asset_id,
                "bpm": analysis_data["primary_bpm"],
                "bpm_conf": analysis_data["bpm_confidence"],
                "candidates": json.dumps(analysis_data["bpm_candidates"]),
                "key": analysis_data["detected_key"],
                "camelot": analysis_data["camelot_code"],
                "key_conf": analysis_data["key_confidence"],
                "lufs": analysis_data["integrated_lufs"],
                "lra": analysis_data["loudness_range_lra"],
                "tp": analysis_data["true_peak_db"],
                "spectral": json.dumps(analysis_data["spectral_summary"]),
                "quality": json.dumps(analysis_data["quality_findings"]),
                "now": datetime.now(timezone.utc),
            },
        )

        # Clear and persist TrackSegments & TrackMatches (Phase 4)
        db.execute(text("DELETE FROM track_segments WHERE mix_id = :mix_id"), {"mix_id": mix_id})
        db.commit()

        for seg in analysis_data.get("track_segments", []):
            seg_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO track_segments (
                        id, mix_id, segment_index, start_time_seconds,
                        end_time_seconds, duration_seconds, fingerprint,
                        confidence, created_at
                    ) VALUES (
                        :id, :mix_id, :idx, :start, :end, :dur, :fp, :conf, :now
                    )
                """),
                {
                    "id": seg_id,
                    "mix_id": mix_id,
                    "idx": seg["segment_index"],
                    "start": seg["start_time_seconds"],
                    "end": seg["end_time_seconds"],
                    "dur": seg["duration_seconds"],
                    "fp": seg.get("fingerprint"),
                    "conf": seg["confidence"],
                    "now": datetime.now(timezone.utc),
                },
            )

            match = seg.get("match")
            if match:
                match_id = str(uuid.uuid4())
                db.execute(
                    text("""
                        INSERT INTO track_matches (
                            id, segment_id, mix_id, title, artist,
                            album, acoustid_id, musicbrainz_recording_id,
                            match_score, source, created_at
                        ) VALUES (
                            :id, :seg_id, :mix_id, :title, :artist,
                            :album, :acoustid, :mb_id, :score, 'acoustid', :now
                        )
                    """),
                    {
                        "id": match_id,
                        "seg_id": seg_id,
                        "mix_id": mix_id,
                        "title": match.get("title", "Unknown Track"),
                        "artist": match.get("artist", "Unknown Artist"),
                        "album": match.get("album"),
                        "acoustid": match.get("acoustid_id"),
                        "mb_id": match.get("musicbrainz_recording_id"),
                        "score": match.get("match_score", 0.8),
                        "now": datetime.now(timezone.utc),
                    },
                )

        # Clear and persist TransitionEvents (Phase 5)
        db.execute(text("DELETE FROM transition_events WHERE mix_id = :mix_id"), {"mix_id": mix_id})
        db.commit()

        for trans in analysis_data.get("transitions", []):
            trans_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO transition_events (
                        id, mix_id, transition_index, start_time_seconds,
                        end_time_seconds, cue_in_time, cue_out_time,
                        transition_type, energy_delta, tempo_shift_bpm,
                        camelot_compatibility, confidence, created_at
                    ) VALUES (
                        :id, :mix_id, :idx, :start, :end, :cue_in, :cue_out,
                        :type, :energy, :tempo, :camelot, :conf, :now
                    )
                """),
                {
                    "id": trans_id,
                    "mix_id": mix_id,
                    "idx": trans["transition_index"],
                    "start": trans["start_time_seconds"],
                    "end": trans["end_time_seconds"],
                    "cue_in": trans["cue_in_time"],
                    "cue_out": trans["cue_out_time"],
                    "type": trans["transition_type"],
                    "energy": trans["energy_delta"],
                    "tempo": trans["tempo_shift_bpm"],
                    "camelot": trans["camelot_compatibility"],
                    "conf": trans["confidence"],
                    "now": datetime.now(timezone.utc),
                },
            )

        db.commit()

        # Finalize Job
        finish_time = datetime.now(timezone.utc)
        db.execute(
            text("UPDATE jobs SET status = 'SUCCEEDED', progress_percent = 100.0, current_stage = 'Complete', finished_at = :finish WHERE id = :id"),
            {"id": job_id, "finish": finish_time},
        )
        db.execute(
            text("UPDATE job_attempts SET status = 'SUCCEEDED', finished_at = :finish WHERE job_id = :id AND status = 'RUNNING'"),
            {"id": job_id, "finish": finish_time},
        )
        db.commit()

        publish_event(job_id, {
            "job_id": job_id,
            "status": "SUCCEEDED",
            "progress_percent": 100.0,
            "current_stage": "Complete",
        })

        return {"status": "ok", "job_id": job_id, "analysis": analysis_data}

    except Exception as e:
        db.rollback()
        fail_time = datetime.now(timezone.utc)
        error_str = str(e)

        db.execute(
            text("UPDATE jobs SET status = 'FAILED', error_message = :err, finished_at = :finish WHERE id = :id"),
            {"id": job_id, "err": error_str, "finish": fail_time},
        )
        db.execute(
            text("UPDATE job_attempts SET status = 'FAILED', error_details = :err, finished_at = :finish WHERE job_id = :id AND status = 'RUNNING'"),
            {"id": job_id, "err": error_str, "finish": fail_time},
        )
        db.commit()

        publish_event(job_id, {
            "job_id": job_id,
            "status": "FAILED",
            "progress_percent": 0.0,
            "error_message": error_str,
        })
        raise e
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Shared bookkeeping for the mastering / stems / sidechain / render pipelines
# ---------------------------------------------------------------------------

def _pipeline_mark_running(db, job_id: str, hostname: str, stage: str = "Initializing") -> None:
    now = datetime.now(timezone.utc)
    db.execute(
        text("UPDATE jobs SET status = 'RUNNING', started_at = :now, current_stage = :stage WHERE id = :id"),
        {"id": job_id, "now": now, "stage": stage},
    )
    db.execute(
        text("UPDATE job_attempts SET status = 'RUNNING', worker_hostname = :host, started_at = :now WHERE job_id = :id AND status = 'QUEUED'"),
        {"id": job_id, "host": hostname, "now": now},
    )
    db.commit()


def _pipeline_progress(db, job_id: str, pct: float, stage: str) -> None:
    db.execute(
        text("UPDATE jobs SET current_stage = :stage, progress_percent = :pct WHERE id = :id"),
        {"id": job_id, "stage": stage, "pct": pct},
    )
    db.commit()
    publish_event(job_id, {
        "job_id": job_id,
        "status": "RUNNING",
        "progress_percent": pct,
        "current_stage": stage,
    })


def _pipeline_mark_finished(db, job_id: str, ok: bool, error: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    final = "SUCCEEDED" if ok else "FAILED"
    db.execute(
        text("UPDATE jobs SET status = :st, progress_percent = :pct, current_stage = :stage, error_message = :err, finished_at = :finish WHERE id = :id"),
        {"id": job_id, "st": final, "pct": 100.0 if ok else 0.0,
         "stage": "Complete" if ok else "Failed", "err": error, "finish": now},
    )
    db.execute(
        text("UPDATE job_attempts SET status = :st, error_details = :err, finished_at = :finish WHERE job_id = :id AND status IN ('RUNNING', 'QUEUED')"),
        {"id": job_id, "st": final, "err": error, "finish": now},
    )
    db.commit()
    publish_event(job_id, {
        "job_id": job_id,
        "status": final,
        "progress_percent": 100.0 if ok else 0.0,
        "current_stage": "Complete" if ok else "Failed",
        **({"error_message": error} if error else {}),
    })


def _resolve_mix_audio(db, mix_id: str) -> tuple[str, Path]:
    """Return (media_asset_id, absolute audio path) or raise FileNotFoundError."""
    row = db.execute(
        text("""
            SELECT m.media_asset_id AS asset_id, a.storage_path AS rel_path
            FROM mixes m JOIN media_assets a ON m.media_asset_id = a.id
            WHERE m.id = :mix
        """),
        {"mix": mix_id},
    ).fetchone()
    if not row:
        raise ValueError(f"Mix {mix_id} not found")
    abs_path = Path(STORAGE_ROOT) / row.rel_path
    if not abs_path.is_file():
        raise FileNotFoundError(f"Audio file for mix {mix_id} missing on storage")
    return row.asset_id, abs_path


@celery_app.task(bind=True, name="tasks.run_mastering_pipeline")
def run_mastering_pipeline(self, job_id: str, mastering_job_id: str):
    """Two-pass loudness mastering with bounded-memory block streaming."""
    db = SessionLocal()
    hostname = socket.gethostname()
    try:
        mjob = db.execute(
            text("SELECT id, media_id, preset_id FROM mastering_jobs WHERE id = :id"),
            {"id": mastering_job_id},
        ).fetchone()
        if not mjob:
            raise ValueError(f"MasteringJob {mastering_job_id} not found")
        preset_key = mjob.preset_id or "sound_system_heavy"
        preset = DEFAULT_PRESETS.get(preset_key, DEFAULT_PRESETS["sound_system_heavy"])

        _, in_abs = _resolve_mix_audio(db, mjob.media_id)
        _pipeline_mark_running(db, job_id, hostname, "Measuring input loudness")

        target_lufs = float(preset["target_lufs"])
        tp_ceiling = float(preset["true_peak_ceiling"])
        input_metrics = measure_program_loudness(in_abs)
        db.execute(
            text("UPDATE mastering_jobs SET status = 'processing', input_lufs = :lufs, input_true_peak = :tp WHERE id = :id"),
            {"id": mastering_job_id, "lufs": input_metrics["integrated_lufs"], "tp": input_metrics["true_peak_db"]},
        )
        db.commit()
        _pipeline_progress(db, job_id, 30.0, "Applying gain and true-peak ceiling")

        gain_db = target_lufs - float(input_metrics["integrated_lufs"])
        gain_lin = 10.0 ** (gain_db / 20.0)
        ceil_lin = 10.0 ** (tp_ceiling / 20.0)
        out_rel = f"assets/derived/{mjob.media_id}_master_{preset_key}.wav"
        out_abs = Path(STORAGE_ROOT) / out_rel
        out_abs.parent.mkdir(parents=True, exist_ok=True)

        with sf.SoundFile(str(in_abs), "r") as fin:
            with sf.SoundFile(
                str(out_abs), "w",
                samplerate=fin.samplerate, channels=fin.channels, subtype="PCM_16",
            ) as fout:
                for block in fin.blocks(blocksize=65536, dtype="float32", always_2d=True):
                    fout.write(np.clip(block * gain_lin, -ceil_lin, ceil_lin))

        _pipeline_progress(db, job_id, 80.0, "Verifying output compliance")
        out_metrics = measure_program_loudness(out_abs)
        compliance = abs(float(out_metrics["integrated_lufs"]) - target_lufs) <= 1.0
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                UPDATE mastering_jobs SET status = 'completed',
                    output_lufs = :lufs, output_true_peak = :tp,
                    output_storage_path = :path, completed_at = :now,
                    metrics = :metrics WHERE id = :id
            """),
            {
                "id": mastering_job_id,
                "lufs": out_metrics["integrated_lufs"], "tp": out_metrics["true_peak_db"],
                "path": out_rel, "now": now,
                "metrics": json.dumps({"gain_adjust_db": round(gain_db, 2), "compliance_passed": compliance}),
            },
        )
        db.commit()
        _pipeline_mark_finished(db, job_id, True)
        return {"status": "ok", "job_id": job_id, "output_path": out_rel, "compliance_passed": compliance}
    except Exception as e:
        db.rollback()
        error_str = str(e)
        try:
            db.execute(
                text("UPDATE mastering_jobs SET status = 'failed' WHERE id = :id"),
                {"id": mastering_job_id},
            )
            db.commit()
        except Exception:
            db.rollback()
        _pipeline_mark_finished(db, job_id, False, error_str)
        raise e
    finally:
        db.close()


def _demucs_available() -> bool:
    return importlib.util.find_spec("demucs") is not None or shutil.which("demucs") is not None


@celery_app.task(bind=True, name="tasks.run_stem_separation")
def run_stem_separation(self, job_id: str, stem_job_id: str):
    """Demucs 4-stem separation (optional dependency) + real bassline analysis."""
    db = SessionLocal()
    hostname = socket.gethostname()
    try:
        sjob = db.execute(
            text("SELECT id, media_id, model_name FROM stem_jobs WHERE id = :id"),
            {"id": stem_job_id},
        ).fetchone()
        if not sjob:
            raise ValueError(f"StemJob {stem_job_id} not found")

        _, in_abs = _resolve_mix_audio(db, sjob.media_id)
        _pipeline_mark_running(db, job_id, hostname, "Checking Demucs availability")

        if not _demucs_available():
            raise RuntimeError(
                "Demucs is not installed in the worker image. Install the optional "
                "separation stack (pip install torch demucs) and retry this job."
            )

        model = sjob.model_name or "htdemucs"
        out_dir = Path(STORAGE_ROOT) / "assets" / "derived" / "stems" / sjob.media_id
        out_dir.mkdir(parents=True, exist_ok=True)
        _pipeline_progress(db, job_id, 15.0, f"Separating stems with {model}")

        cmd = [sys.executable, "-m", "demucs", "-n", model, "--out", str(out_dir), str(in_abs)]
        subprocess.run(cmd, check=True, timeout=3500, capture_output=True, text=True)

        _pipeline_progress(db, job_id, 75.0, "Analyzing kick/sub collision")
        # Demucs layout: <out>/<model>/<track_stem>/{drums,bass,other,vocals}.wav
        candidates = [p for p in out_dir.rglob("drums.wav")]
        stem_base = candidates[0].parent if candidates else None
        paths: dict[str, str | None] = {}
        for stem in ("drums", "bass", "other", "vocals"):
            src = stem_base / f"{stem}.wav" if stem_base else None
            if src is not None and src.is_file():
                rel = str(src.relative_to(STORAGE_ROOT))
                paths[stem] = rel
            else:
                paths[stem] = None

        bass_fundamental: float | None = None
        collision: float | None = None
        peaks: list = []
        if paths["drums"] and paths["bass"]:
            def _load_mono(rel: str, seconds: int = 30):
                with sf.SoundFile(str(Path(STORAGE_ROOT) / rel), "r") as f:
                    frames = min(len(f), seconds * f.samplerate)
                    data = f.read(frames, dtype="float32", always_2d=True)
                    return data.mean(axis=1), f.samplerate

            drums, sr = _load_mono(paths["drums"])
            bass, _ = _load_mono(paths["bass"])
            analysis = StemSeparatorEngine.analyze_bassline_and_collision(bass, drums, sr)
            bass_fundamental = analysis.get("bass_fundamental_hz")
            collision = analysis.get("kick_sub_collision_score")
            peaks = analysis.get("resonance_peaks", [])

        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                UPDATE stem_jobs SET status = 'completed',
                    drums_path = :drums, bass_path = :bass,
                    other_path = :other, vocals_path = :vocals,
                    bass_fundamental_hz = :fund,
                    kick_sub_collision_score = :coll,
                    resonance_peaks = :peaks, completed_at = :now
                WHERE id = :id
            """),
            {
                "id": stem_job_id, "drums": paths["drums"], "bass": paths["bass"],
                "other": paths["other"], "vocals": paths["vocals"],
                "fund": bass_fundamental, "coll": collision,
                "peaks": json.dumps(peaks), "now": now,
            },
        )
        db.commit()
        _pipeline_mark_finished(db, job_id, True)
        return {"status": "ok", "job_id": job_id, "stems": paths}
    except Exception as e:
        db.rollback()
        error_str = str(e)
        try:
            db.execute(text("UPDATE stem_jobs SET status = 'failed' WHERE id = :id"), {"id": stem_job_id})
            db.commit()
        except Exception:
            db.rollback()
        _pipeline_mark_finished(db, job_id, False, error_str)
        raise e
    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.run_sidechain")
def run_sidechain(self, job_id: str, sidechain_job_id: str):
    """Kick/sub sidechain ducking on real separated stems (requires stems first)."""
    db = SessionLocal()
    hostname = socket.gethostname()
    try:
        scj = db.execute(
            text("SELECT id, media_id, threshold_db, max_ducking_db FROM sidechain_jobs WHERE id = :id"),
            {"id": sidechain_job_id},
        ).fetchone()
        if not scj:
            raise ValueError(f"SidechainJob {sidechain_job_id} not found")

        stem = db.execute(
            text("""
                SELECT drums_path, bass_path FROM stem_jobs
                WHERE media_id = :mix AND status = 'completed'
                ORDER BY completed_at DESC LIMIT 1
            """),
            {"mix": scj.media_id},
        ).fetchone()
        drums_abs = Path(STORAGE_ROOT) / stem.drums_path if stem and stem.drums_path else None
        bass_abs = Path(STORAGE_ROOT) / stem.bass_path if stem and stem.bass_path else None
        if not stem or not drums_abs or not bass_abs or not drums_abs.is_file() or not bass_abs.is_file():
            raise RuntimeError(
                "Sidechain requires a completed stem separation with drums/bass "
                "files on storage. Run stem separation for this mix first."
            )

        _pipeline_mark_running(db, job_id, hostname, "Loading isolated stems")

        def _load_mono(abs_path: Path, seconds: int = 60):
            with sf.SoundFile(str(abs_path), "r") as f:
                frames = min(len(f), seconds * f.samplerate)
                data = f.read(frames, dtype="float32", always_2d=True)
                return data.mean(axis=1), f.samplerate

        kick, sr = _load_mono(drums_abs)
        bass, _ = _load_mono(bass_abs)
        result = DynamicSidechainDSP.process_sub_bass_sidechain(
            kick_audio=kick,
            bass_audio=bass,
            sample_rate=sr,
            threshold_db=float(scj.threshold_db if scj.threshold_db is not None else -12.0),
            max_ducking_db=float(scj.max_ducking_db if scj.max_ducking_db is not None else 6.0),
        )

        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                UPDATE sidechain_jobs SET status = 'completed',
                    phase_inverted = :inv, phase_correlation = :corr,
                    max_gain_reduction_db = :gr, processed_bass_rms = :rms,
                    low_end_clarity_score = :clarity, completed_at = :now
                WHERE id = :id
            """),
            {
                "id": sidechain_job_id, "inv": result["phase_inverted"],
                "corr": result["phase_correlation"], "gr": result["max_gain_reduction_db"],
                "rms": result["processed_bass_rms"], "clarity": result["low_end_clarity_score"],
                "now": now,
            },
        )
        db.commit()
        _pipeline_mark_finished(db, job_id, True)
        return {"status": "ok", "job_id": job_id, **result}
    except Exception as e:
        db.rollback()
        error_str = str(e)
        try:
            db.execute(
                text("UPDATE sidechain_jobs SET status = 'failed', error_message = :err WHERE id = :id"),
                {"id": sidechain_job_id, "err": error_str},
            )
            db.commit()
        except Exception:
            db.rollback()
        _pipeline_mark_finished(db, job_id, False, error_str)
        raise e
    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.run_broadcast_render")
def run_broadcast_render(self, job_id: str, mix_id: str, params: dict):
    """Render the 16:9 1080p audio-reactive broadcast file with FFmpeg."""
    db = SessionLocal()
    hostname = socket.gethostname()
    try:
        row = db.execute(
            text("""
                SELECT m.title AS title, a.storage_path AS rel_path,
                       an.primary_bpm AS bpm, an.camelot_code AS camelot
                FROM mixes m
                JOIN media_assets a ON m.media_asset_id = a.id
                LEFT JOIN analysis_results an ON an.mix_id = m.id
                WHERE m.id = :mix
            """),
            {"mix": mix_id},
        ).fetchone()
        if not row:
            raise ValueError(f"Mix {mix_id} not found")
        in_abs = Path(STORAGE_ROOT) / row.rel_path
        if not in_abs.is_file():
            raise FileNotFoundError(f"Audio file for mix {mix_id} missing on storage")

        title = params.get("stream_title") or row.title or "Live Set"
        artist = params.get("artist_name") or "SYSTEM CORRUPT"
        bpm = float(params.get("bpm") or row.bpm or 150.0)
        camelot = params.get("camelot_key") or row.camelot or "8A"
        out_rel = f"assets/derived/broadcast/{mix_id}_1080p.mp4"
        out_abs = Path(STORAGE_ROOT) / out_rel
        out_abs.parent.mkdir(parents=True, exist_ok=True)

        _pipeline_mark_running(db, job_id, hostname, "Rendering 1080p broadcast")

        filter_complex = FFmpegBroadcastCompositor.build_filter_complex(
            title=title, artist=artist, bpm=bpm, camelot_key=camelot
        )
        cmd = FFmpegBroadcastCompositor.build_ffmpeg_command(
            input_audio=str(in_abs), output_dest=str(out_abs),
            title=title, artist=artist, bpm=bpm, camelot_key=camelot,
        )
        subprocess.run(cmd, check=True, timeout=3500, capture_output=True, text=True)
        _pipeline_progress(db, job_id, 90.0, "Registering broadcast output")

        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO broadcast_syncs (
                    id, media_id, station_id, playlist_name, status,
                    cue_markers_synced, details, synced_at
                ) VALUES (
                    :id, :mix, :station, :playlist, 'rendered', 0, :details, :now
                )
            """),
            {
                "id": str(uuid.uuid4()), "mix": mix_id,
                "station": params.get("station_id") or "syco23_live",
                "playlist": params.get("playlist_name") or "Underground Freetekno Sets",
                "details": json.dumps({"output_path": out_rel, "title": title, "artist": artist}),
                "now": now,
            },
        )
        db.commit()
        _pipeline_mark_finished(db, job_id, True)
        return {"status": "ok", "job_id": job_id, "output_path": out_rel}
    except Exception as e:
        db.rollback()
        error_str = str(e)
        _pipeline_mark_finished(db, job_id, False, error_str)
        raise e
    finally:
        db.close()
