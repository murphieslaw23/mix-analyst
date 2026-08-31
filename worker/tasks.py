import os
import json
import socket
import redis
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import text
from .celery_app import celery_app
from .db import SessionLocal
from .analysis.orchestrator import AudioAnalysisOrchestrator

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
    Execute the real bounded-memory audio analysis pipeline for a Mix.
    Calculates BPM, Camelot Key, and EBU R128 loudness, then persists results.
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
