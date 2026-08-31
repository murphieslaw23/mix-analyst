import os
import json
import time
import socket
import redis
from datetime import datetime, timezone
from sqlalchemy import text
from .celery_app import celery_app
from .db import SessionLocal

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
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
    Execute the asynchronous analysis pipeline stages for a Mix.
    Updates PostgreSQL Job and StageRun records and publishes live SSE updates.
    """
    db = SessionLocal()
    hostname = socket.gethostname()
    start_time = datetime.now(timezone.utc)

    try:
        # 1. Fetch Job and Mix details
        job_row = db.execute(
            text("SELECT id, mix_id, status FROM jobs WHERE id = :id"),
            {"id": job_id},
        ).fetchone()

        if not job_row:
            return {"status": "error", "message": f"Job {job_id} not found"}

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

        publish_event(job_id, {
            "job_id": job_id,
            "status": "RUNNING",
            "progress_percent": 5.0,
            "current_stage": "Initializing pipeline",
        })

        # Define pipeline stages
        stages = [
            ("stage_probe_validation", "Stream Validation & Structural Probe", 20.0),
            ("stage_windowing_plan", "Representative Windowing Matrix", 40.0),
            ("stage_tempo_harmonic", "BPM & Camelot Harmonic Analysis", 70.0),
            ("stage_loudness_profile", "Integrated LUFS & True Peak Pass", 90.0),
            ("stage_finalization", "Persisting Results & Tag Aggregation", 100.0),
        ]

        for stage_name, stage_label, target_progress in stages:
            stage_start = datetime.now(timezone.utc)
            stage_id = f"{job_id}_{stage_name}"

            # Register StageRun in DB
            db.execute(
                text("""
                    INSERT INTO stage_runs (id, job_id, stage_name, stage_version, status, progress_percent, started_at)
                    VALUES (:id, :job_id, :name, '1.0.0', 'RUNNING', :progress, :now)
                    ON CONFLICT (id) DO UPDATE SET status = 'RUNNING', started_at = :now
                """),
                {"id": stage_id, "job_id": job_id, "name": stage_label, "progress": target_progress, "now": stage_start},
            )
            db.execute(
                text("UPDATE jobs SET current_stage = :stage, progress_percent = :progress WHERE id = :id"),
                {"id": job_id, "stage": stage_label, "progress": target_progress},
            )
            db.commit()

            publish_event(job_id, {
                "job_id": job_id,
                "status": "RUNNING",
                "progress_percent": target_progress,
                "current_stage": stage_label,
            })

            # Stage execution simulation delay for Phase 2 pipeline verification
            time.sleep(1.2)

            # Complete StageRun
            stage_finish = datetime.now(timezone.utc)
            db.execute(
                text("UPDATE stage_runs SET status = 'COMPLETED', finished_at = :finish WHERE id = :id"),
                {"id": stage_id, "finish": stage_finish},
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

        return {"status": "ok", "job_id": job_id}

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
