import os
import json
import socket
import uuid
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import text
from .celery_app import celery_app
from .db import SessionLocal
from .analysis.orchestrator import AudioAnalysisOrchestrator
from api.app.models.job import Job, JobStatus
from api.app.services.job_commands import claim_job_attempt
from api.app.services.job_events import event_notification, publish_event
from api.app.services.job_events_store import record_job_event

STORAGE_ROOT = os.getenv("STORAGE_ROOT", "/data/storage")


class JobStopped(Exception):
    """The authoritative job state no longer permits worker-side processing."""


def require_running_job(db, job_id: str, project_id: str) -> None:
    """Stop cooperative work once cancellation or another terminal state wins."""
    status = db.execute(
        text("SELECT status FROM jobs WHERE id = :id AND project_id = :project_id"),
        {"id": job_id, "project_id": project_id},
    ).scalar_one_or_none()
    if status != "RUNNING":
        raise JobStopped(f"Job {job_id} is no longer running")


def transition_job_and_attempt(db, job_id: str, project_id: str, terminal_status: JobStatus, error: str | None = None) -> bool:
    """Terminally transition a scoped job and its running attempt together.

    The job update is the authoritative cancellation race gate.  An attempt is
    updated only after that gate wins, and its query verifies the same project
    and terminal job state while the job-row lock remains in this transaction.
    """
    if terminal_status not in (JobStatus.SUCCEEDED, JobStatus.FAILED):
        raise ValueError("Only successful or failed terminal transitions are supported")

    finish_time = datetime.now(timezone.utc)
    if terminal_status is JobStatus.SUCCEEDED:
        job_result = db.execute(
            text(
                "UPDATE jobs SET status = :status, progress_percent = 100.0, "
                "current_stage = 'Complete', finished_at = :finish "
                "WHERE id = :id AND project_id = :project_id AND status = 'RUNNING' RETURNING id"
            ),
            {"id": job_id, "project_id": project_id, "status": terminal_status.value, "finish": finish_time},
        ).scalar_one_or_none()
    else:
        job_result = db.execute(
            text(
                "UPDATE jobs SET status = :status, error_message = :error, finished_at = :finish "
                "WHERE id = :id AND project_id = :project_id AND status = 'RUNNING' RETURNING id"
            ),
            {
                "id": job_id,
                "project_id": project_id,
                "status": terminal_status.value,
                "error": error,
                "finish": finish_time,
            },
        ).scalar_one_or_none()
    if job_result is None:
        return False

    attempt_result = db.execute(
        text(
            "UPDATE job_attempts SET status = :status, error_details = :error, finished_at = :finish "
            "WHERE job_id = :id AND status = 'RUNNING' "
            "AND EXISTS (SELECT 1 FROM jobs "
            "WHERE jobs.id = job_attempts.job_id AND jobs.project_id = :project_id AND jobs.status = :status) "
            "RETURNING id"
        ),
        {
            "id": job_id,
            "project_id": project_id,
            "status": terminal_status.value,
            "error": error,
            "finish": finish_time,
        },
    ).scalar_one_or_none()
    if attempt_result is None:
        raise RuntimeError(f"Running job {job_id} has no running attempt to finalize")

    job = db.get(Job, job_id)
    db.refresh(job)
    record_job_event(
        db,
        job,
        "update",
        {
            "job_id": job_id,
            "status": terminal_status.value,
            "progress_percent": job.progress_percent,
            "current_stage": job.current_stage,
            "error_message": error,
        },
    )
    return True


@celery_app.task(bind=True, name="tasks.run_analysis_pipeline")
def run_analysis_pipeline(self, job_id: str, project_id: str):
    """
    Execute the real bounded-memory audio analysis, fingerprinting & transition detection pipeline.
    """
    db = SessionLocal()
    hostname = socket.gethostname()
    try:
        # A broker message is at-least-once.  The conditional claim lets only
        # one worker begin, including after a dispatcher restart/redelivery.
        if claim_job_attempt(db, job_id, hostname, project_id) is None:
            db.rollback()
            return {"status": "already_claimed", "job_id": job_id}
        running_job = db.get(Job, job_id)
        running_event = record_job_event(
            db,
            running_job,
            "update",
            {
                "job_id": job_id,
                "status": JobStatus.RUNNING.value,
                "progress_percent": running_job.progress_percent,
                "current_stage": running_job.current_stage,
            },
        )
        db.commit()
        publish_event(project_id, job_id, event_notification(running_event))

        # 1. Fetch Job and Mix details
        job_row = db.execute(
            text("""
                SELECT j.id, j.mix_id, m.media_asset_id, a.storage_path, a.duration_seconds
                FROM jobs j
                JOIN mixes m ON j.mix_id = m.id AND m.project_id = j.project_id
                JOIN media_assets a ON m.media_asset_id = a.id AND a.project_id = j.project_id
                WHERE j.id = :id AND j.project_id = :project_id
            """),
            {"id": job_id, "project_id": project_id},
        ).fetchone()

        if not job_row:
            return {"status": "error", "message": f"Job {job_id} not found"}

        mix_id = job_row.mix_id
        media_asset_id = job_row.media_asset_id
        storage_rel_path = job_row.storage_path
        duration_seconds = float(job_row.duration_seconds)
        audio_abs_path = Path(STORAGE_ROOT) / storage_rel_path

        def progress_tracker(pct: float, stage_name: str):
            require_running_job(db, job_id, project_id)
            progress_result = db.execute(
                text("UPDATE jobs SET current_stage = :stage, progress_percent = :pct WHERE id = :id AND project_id = :project_id AND status = 'RUNNING'"),
                {"id": job_id, "project_id": project_id, "stage": stage_name, "pct": pct},
            )
            if progress_result.rowcount != 1:
                raise JobStopped(f"Job {job_id} is no longer running")
            progress_job = db.get(Job, job_id)
            progress_event = record_job_event(
                db,
                progress_job,
                "update",
                {
                    "job_id": job_id,
                    "status": JobStatus.RUNNING.value,
                    "progress_percent": pct,
                    "current_stage": stage_name,
                },
            )
            db.commit()
            publish_event(project_id, job_id, event_notification(progress_event))

        # Run real orchestrator. Its progress callbacks provide cooperative
        # cancellation checkpoints during bounded processing.
        require_running_job(db, job_id, project_id)
        orchestrator = AudioAnalysisOrchestrator(audio_abs_path, duration_seconds)
        analysis_data = orchestrator.execute_pipeline(progress_callback=progress_tracker)

        # Persist AnalysisResult in DB
        require_running_job(db, job_id, project_id)
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
        require_running_job(db, job_id, project_id)
        db.execute(text("DELETE FROM track_segments WHERE mix_id = :mix_id"), {"mix_id": mix_id})
        db.commit()

        for seg in analysis_data.get("track_segments", []):
            require_running_job(db, job_id, project_id)
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
        require_running_job(db, job_id, project_id)
        db.execute(text("DELETE FROM transition_events WHERE mix_id = :mix_id"), {"mix_id": mix_id})
        db.commit()

        for trans in analysis_data.get("transitions", []):
            require_running_job(db, job_id, project_id)
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

        require_running_job(db, job_id, project_id)
        db.commit()

        # Finalize the attempt only if this scoped job still wins the
        # authoritative RUNNING -> SUCCEEDED transition.
        if not transition_job_and_attempt(db, job_id, project_id, JobStatus.SUCCEEDED):
            db.rollback()
            return {"status": "cancelled", "job_id": job_id}
        terminal_event = db.query(Job).filter(Job.id == job_id).one().events[-1]
        db.commit()
        publish_event(project_id, job_id, event_notification(terminal_event))

        return {"status": "ok", "job_id": job_id, "analysis": analysis_data}

    except JobStopped:
        db.rollback()
        return {"status": "cancelled", "job_id": job_id}
    except Exception as e:
        db.rollback()
        error_str = str(e)
        if not transition_job_and_attempt(db, job_id, project_id, JobStatus.FAILED, error_str):
            db.rollback()
            return {"status": "cancelled", "job_id": job_id}
        terminal_event = db.query(Job).filter(Job.id == job_id).one().events[-1]
        db.commit()
        publish_event(project_id, job_id, event_notification(terminal_event))
        raise e
    finally:
        db.close()
