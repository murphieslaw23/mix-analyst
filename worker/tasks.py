import json
import math
import os
import socket
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

from api.app.config import settings as app_settings
from api.app.models.artifact import Artifact as ArtifactRecord
from api.app.models.job import Job, JobAttempt, JobStatus, StageRun, StageStatus
from api.app.models.job_event import JobEvent
from api.app.services.batches import advance_batch_after_terminal_job
from api.app.services.job_commands import claim_job_attempt, heartbeat_job_attempt
from api.app.services.job_events import event_notification, publish_event
from api.app.services.job_events_store import (
    complete_job_attempt,
    database_current_timestamp,
    record_job_event,
)
from api.app.services.notifications import create_job_notification
from api.app.services.storage import StorageService
from api.app.services.upload_sessions import (
    cleanup_expired_uploads_global,
    reconcile_pending_upload_promotions,
)

from .analysis.orchestrator import AudioAnalysisOrchestrator
from .celery_app import celery_app
from .db import SessionLocal
from .services.metrics import record_job_finished, record_job_started, started_at
from .stages.generate_waveform import generate_waveform
from .stages.master_mix import MasterSettings
from .stages.master_mix import run_master_mix as run_master_mix_stage
from .stages.tag_mix import Artifact as StageArtifact
from .stages.tag_mix import tag_mix

# API, Compose, and every worker role use the same declared settings alias.
# ``STORAGE_ROOT`` existed only as an undocumented worker-only spelling and
# caused deployed workers to read a different volume than uploads wrote.
STORAGE_ROOT = app_settings.storage_root


class JobStopped(Exception):
    """The authoritative job state no longer permits worker-side processing."""


class AttemptLeaseUnavailable(Exception):
    """A duplicate delivery arrived while another fenced worker is live."""

    def __init__(self, countdown: int):
        self.countdown = countdown
        super().__init__(f"attempt lease remains active; retry in {countdown}s")


def require_running_job(
    db,
    job_id: str,
    project_id: str,
    attempt_number: int | None = None,
    claim_token: str | None = None,
) -> None:
    """Stop cooperative work once cancellation or another terminal state wins."""
    status = db.execute(
        text("SELECT status FROM jobs WHERE id = :id AND project_id = :project_id"),
        {"id": job_id, "project_id": project_id},
    ).scalar_one_or_none()
    if status != "RUNNING":
        raise JobStopped(f"Job {job_id} is no longer running")
    if (
        attempt_number is not None
        and claim_token is not None
        and not heartbeat_job_attempt(
            db, job_id, project_id, attempt_number, claim_token
        )
    ):
        raise JobStopped(f"Job {job_id} attempt lease is no longer active")


def _claim_task_attempt(
    self, db, job_id: str, project_id: str, hostname: str, attempt_number: int | None
):
    """Claim an exact dispatched attempt and retain its fencing identity."""
    # Celery's request id belongs to the broker message and is preserved by
    # ``retry``/redelivery. It is therefore not a fencing token. Every process
    # execution receives a new opaque token, so a reclaimed lease can reject
    # an older process even when it runs on the same hostname.
    claim_token = uuid.uuid4().hex
    if attempt_number is None:
        # Direct task invocation remains useful in existing developer tests;
        # normal broker dispatches always carry the attempt number below.
        attempt = claim_job_attempt(
            db, job_id, hostname, project_id, claim_token=claim_token
        )
    else:
        attempt = claim_job_attempt(
            db,
            job_id,
            hostname,
            project_id,
            attempt_number=attempt_number,
            claim_token=claim_token,
        )
    if attempt is None:
        # A late/duplicate broker delivery cannot be acknowledged as a normal
        # success while a live lease owns the job. Schedule a bounded-delay
        # retry, giving that lease a chance to expire and be reclaimed after a
        # worker loss. Terminal or superseded attempts still ACK idempotently.
        if attempt_number is not None:
            active = db.scalar(
                select(JobAttempt)
                .join(Job, Job.id == JobAttempt.job_id)
                .where(
                    JobAttempt.job_id == job_id,
                    JobAttempt.attempt_number == attempt_number,
                    JobAttempt.status == JobStatus.RUNNING,
                    Job.project_id == project_id,
                )
            )
            if active is not None and active.lease_expires_at is not None:
                expires_at = active.lease_expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
                if remaining > 0:
                    raise AttemptLeaseUnavailable(max(1, min(60, math.ceil(remaining))))
        return None
    return attempt.attempt_number, attempt.claim_token


def latest_job_event(db, job_id: str, project_id: str) -> JobEvent:
    """Load the latest event only from the worker's trusted project scope."""
    event = db.scalar(
        select(JobEvent)
        .where(JobEvent.job_id == job_id, JobEvent.project_id == project_id)
        .order_by(JobEvent.sequence.desc())
        .limit(1)
    )
    if event is None:
        raise RuntimeError(f"Job {job_id} has no durable event in project {project_id}")
    return event


def owner_scoped_artifact_key(project_id: str, relative_key: str) -> str:
    """Attach a pure-stage identity to its owner's immutable key namespace."""
    if not relative_key.startswith("artifacts/"):
        raise ValueError("artifact key must be a relative artifact identity")
    return f"projects/{project_id}/{relative_key}"


def persist_immutable_payload(storage_root: str, key: str, payload: bytes) -> None:
    """Link a completed immutable payload once, preserving retry idempotency."""
    storage = StorageService(storage_root)
    destination = storage.object_path(key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = storage.object_path(".staging")
    staging.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix="artifact-", dir=staging)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.read_bytes() != payload:
                raise RuntimeError(
                    "immutable artifact key already contains different bytes"
                )
    finally:
        if temporary.exists():
            temporary.unlink()


def persist_artifact_record(
    db,
    *,
    project_id: str,
    mix_id: str,
    artifact: StageArtifact,
    key: str,
    report: dict | None = None,
):
    """Attach an immutable object to one mix without replacing other attachments."""
    existing = db.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.project_id == project_id,
            ArtifactRecord.mix_id == mix_id,
            ArtifactRecord.key == key,
        )
    )
    if existing is not None:
        immutable_fields = (
            "role",
            "sha256",
            "algorithm_version",
            "media_type",
            "byte_length",
        )
        expected = (
            artifact.role,
            artifact.sha256,
            artifact.algorithm_version,
            artifact.media_type,
            artifact.byte_length,
        )
        actual = tuple(getattr(existing, field) for field in immutable_fields)
        if actual != expected:
            raise RuntimeError(
                "immutable artifact record conflicts with its existing identity"
            )
        return existing
    record = ArtifactRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        mix_id=mix_id,
        role=artifact.role,
        key=key,
        sha256=artifact.sha256,
        algorithm_version=artifact.algorithm_version,
        media_type=artifact.media_type,
        byte_length=artifact.byte_length,
        report=report,
    )
    db.add(record)
    return record


def transition_job_and_attempt(
    db,
    job_id: str,
    project_id: str,
    worker_name: str,
    terminal_status: JobStatus,
    error: str | None = None,
    attempt_number: int | None = None,
    claim_token: str | None = None,
) -> bool:
    """Terminally transition a scoped job and its running attempt together.

    The job update is the authoritative cancellation race gate.  An attempt is
    updated only after that gate wins, and its query verifies the same project
    and terminal job state while the job-row lock remains in this transaction.
    """
    if terminal_status not in (JobStatus.SUCCEEDED, JobStatus.FAILED):
        raise ValueError("Only successful or failed terminal transitions are supported")

    # The lease condition must observe time at conditional-update evaluation,
    # not at task entry: PostgreSQL may wait for a competing row lock long
    # enough for the worker lease to expire. ``clock_timestamp()`` is volatile
    # on PostgreSQL; SQLite uses its statement timestamp under its single
    # writer lock.
    finish_time = str(
        database_current_timestamp(db).compile(dialect=db.get_bind().dialect)
    )
    if terminal_status is JobStatus.SUCCEEDED:
        job_result = db.execute(
            text(
                "UPDATE jobs SET status = :status, progress_percent = 100.0, "
                f"current_stage = 'Complete', finished_at = {finish_time} "
                "WHERE id = :id AND project_id = :project_id AND status = 'RUNNING' "
                "AND EXISTS (SELECT 1 FROM job_attempts WHERE job_attempts.job_id = jobs.id "
                "AND job_attempts.status = 'RUNNING' AND job_attempts.worker_hostname = :worker_name "
                "AND (:attempt_number IS NULL OR job_attempts.attempt_number = :attempt_number) "
                "AND (:claim_token IS NULL OR job_attempts.claim_token = :claim_token) "
                f"AND job_attempts.lease_expires_at > {finish_time}) RETURNING id"
            ),
            {
                "id": job_id,
                "project_id": project_id,
                "worker_name": worker_name,
                "status": terminal_status.value,
                "attempt_number": attempt_number,
                "claim_token": claim_token,
            },
        ).scalar_one_or_none()
    else:
        job_result = db.execute(
            text(
                f"UPDATE jobs SET status = :status, error_message = :error, finished_at = {finish_time} "
                "WHERE id = :id AND project_id = :project_id AND status = 'RUNNING' "
                "AND EXISTS (SELECT 1 FROM job_attempts WHERE job_attempts.job_id = jobs.id "
                "AND job_attempts.status = 'RUNNING' AND job_attempts.worker_hostname = :worker_name "
                "AND (:attempt_number IS NULL OR job_attempts.attempt_number = :attempt_number) "
                "AND (:claim_token IS NULL OR job_attempts.claim_token = :claim_token) "
                f"AND job_attempts.lease_expires_at > {finish_time}) RETURNING id"
            ),
            {
                "id": job_id,
                "project_id": project_id,
                "worker_name": worker_name,
                "status": terminal_status.value,
                "error": error,
                "attempt_number": attempt_number,
                "claim_token": claim_token,
            },
        ).scalar_one_or_none()
    if job_result is None:
        return False

    attempt_result = db.execute(
        text(
            f"UPDATE job_attempts SET status = :status, error_details = :error, finished_at = {finish_time} "
            "WHERE job_id = :id AND status = 'RUNNING' AND worker_hostname = :worker_name "
            "AND (:attempt_number IS NULL OR attempt_number = :attempt_number) "
            "AND (:claim_token IS NULL OR claim_token = :claim_token) "
            f"AND lease_expires_at > {finish_time} "
            "AND EXISTS (SELECT 1 FROM jobs "
            "WHERE jobs.id = job_attempts.job_id AND jobs.project_id = :project_id AND jobs.status = :status) "
            "RETURNING id"
        ),
        {
            "id": job_id,
            "project_id": project_id,
            "status": terminal_status.value,
            "worker_name": worker_name,
            "error": error,
            "attempt_number": attempt_number,
            "claim_token": claim_token,
        },
    ).scalar_one_or_none()
    if attempt_result is None:
        raise RuntimeError(f"Running job {job_id} has no running attempt to finalize")

    job = db.scalar(select(Job).where(Job.id == job_id, Job.project_id == project_id))
    if job is None:
        raise RuntimeError(f"Terminal job {job_id} is outside project {project_id}")
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
    create_job_notification(db, job)
    return True


def publish_analysis_results(
    db,
    *,
    job_id: str,
    project_id: str,
    hostname: str,
    attempt_number: int | None,
    claim_token: str | None,
    mix_id: str,
    media_asset_id: str,
    analysis_data: dict,
    source_artifact: StageArtifact,
    source_key: str,
    tagged_mix,
    metadata_key: str,
    waveform,
    waveform_key: str,
) -> JobEvent:
    """Publish a complete analysis replacement only when its attempt succeeds.

    All user-visible rows (analysis, tracks, transitions, artifact attachments,
    completed stage reports, and terminal state) share one savepoint.  An old
    successful result therefore survives a cancellation or stale worker that
    loses the final fencing check.  Immutable files written before this point
    are harmless until an attachment makes them reachable.
    """
    with db.begin_nested():
        analysis_id = f"analysis_{mix_id}"
        db.execute(
            text(
                """
                INSERT INTO analysis_results (
                    id, mix_id, media_asset_id, primary_bpm, bpm_confidence,
                    bpm_candidates, detected_key, camelot_code, key_confidence,
                    integrated_lufs, loudness_range_lra, true_peak_db,
                    spectral_summary, quality_findings, created_at
                ) VALUES (
                    :id, :mix_id, :asset_id, :bpm, :bpm_conf,
                    :candidates, :key, :camelot, :key_conf,
                    :lufs, :lra, :tp, :spectral, :quality, :now
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
                """
            ),
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

        # Replace dependent rows only inside this publication savepoint.
        db.execute(
            text("DELETE FROM track_matches WHERE mix_id = :mix_id"), {"mix_id": mix_id}
        )
        db.execute(
            text("DELETE FROM track_segments WHERE mix_id = :mix_id"),
            {"mix_id": mix_id},
        )
        for segment in analysis_data.get("track_segments", []):
            segment_id = str(uuid.uuid4())
            db.execute(
                text(
                    """
                    INSERT INTO track_segments (
                        id, mix_id, segment_index, start_time_seconds,
                        end_time_seconds, duration_seconds, fingerprint,
                        confidence, created_at
                    ) VALUES (
                        :id, :mix_id, :idx, :start, :end, :dur, :fp, :conf, :now
                    )
                    """
                ),
                {
                    "id": segment_id,
                    "mix_id": mix_id,
                    "idx": segment["segment_index"],
                    "start": segment["start_time_seconds"],
                    "end": segment["end_time_seconds"],
                    "dur": segment["duration_seconds"],
                    "fp": segment.get("fingerprint"),
                    "conf": segment["confidence"],
                    "now": datetime.now(timezone.utc),
                },
            )
            match = segment.get("match")
            if match:
                db.execute(
                    text(
                        """
                        INSERT INTO track_matches (
                            id, segment_id, mix_id, title, artist, album,
                            acoustid_id, musicbrainz_recording_id, match_score,
                            source, created_at
                        ) VALUES (
                            :id, :segment_id, :mix_id, :title, :artist, :album,
                            :acoustid, :mb_id, :score, 'acoustid', :now
                        )
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "segment_id": segment_id,
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

        db.execute(
            text("DELETE FROM transition_events WHERE mix_id = :mix_id"),
            {"mix_id": mix_id},
        )
        for transition in analysis_data.get("transitions", []):
            db.execute(
                text(
                    """
                    INSERT INTO transition_events (
                        id, mix_id, transition_index, start_time_seconds,
                        end_time_seconds, cue_in_time, cue_out_time,
                        transition_type, energy_delta, tempo_shift_bpm,
                        camelot_compatibility, confidence, created_at
                    ) VALUES (
                        :id, :mix_id, :idx, :start, :end, :cue_in, :cue_out,
                        :type, :energy, :tempo, :camelot, :conf, :now
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "mix_id": mix_id,
                    "idx": transition["transition_index"],
                    "start": transition["start_time_seconds"],
                    "end": transition["end_time_seconds"],
                    "cue_in": transition["cue_in_time"],
                    "cue_out": transition["cue_out_time"],
                    "type": transition["transition_type"],
                    "energy": transition["energy_delta"],
                    "tempo": transition["tempo_shift_bpm"],
                    "camelot": transition["camelot_compatibility"],
                    "conf": transition["confidence"],
                    "now": datetime.now(timezone.utc),
                },
            )

        persist_artifact_record(
            db,
            project_id=project_id,
            mix_id=mix_id,
            artifact=source_artifact,
            key=source_key,
        )
        persist_artifact_record(
            db,
            project_id=project_id,
            mix_id=mix_id,
            artifact=tagged_mix.metadata_artifact,
            key=metadata_key,
            report={
                "suggested_download_name": tagged_mix.suggested_download_name,
                **tagged_mix.report.as_dict(),
            },
        )
        waveform_descriptor = StageArtifact(
            role=waveform.role,
            key=waveform.key,
            sha256=waveform.sha256,
            algorithm_version=waveform.algorithm_version,
            media_type=waveform.media_type,
            byte_length=waveform.byte_length,
        )
        persist_artifact_record(
            db,
            project_id=project_id,
            mix_id=mix_id,
            artifact=waveform_descriptor,
            key=waveform_key,
            report={
                "points": waveform.points,
                "duration_seconds": waveform.duration_seconds,
            },
        )
        db.add_all(
            [
                StageRun(
                    id=str(uuid.uuid4()),
                    job_id=job_id,
                    stage_name="tag_mix",
                    stage_version="v1",
                    status=StageStatus.COMPLETED,
                    progress_percent=100.0,
                    stage_output=json.dumps(
                        {
                            "artifact_key": metadata_key,
                            "suggested_download_name": tagged_mix.suggested_download_name,
                        }
                    ),
                    finished_at=datetime.now(timezone.utc),
                ),
                StageRun(
                    id=str(uuid.uuid4()),
                    job_id=job_id,
                    stage_name="generate_waveform",
                    stage_version="v1",
                    status=StageStatus.COMPLETED,
                    progress_percent=100.0,
                    stage_output=json.dumps(
                        {"artifact_key": waveform_key, "points": waveform.points}
                    ),
                    finished_at=datetime.now(timezone.utc),
                ),
            ]
        )
        if not complete_job_attempt(
            db, job_id, project_id, hostname, attempt_number, claim_token
        ):
            raise JobStopped(f"Job {job_id} lost its terminal publication race")
        advance_batch_after_terminal_job(db, job_id, project_id)
        return latest_job_event(db, job_id, project_id)


@celery_app.task(bind=True, name="tasks.run_master_mix", max_retries=None)
def run_master_mix(
    self, job_id: str, project_id: str, attempt_number: int | None = None
):
    """Run a MASTERING command as an immutable worker-owned artifact stage."""
    db = SessionLocal()
    hostname = socket.gethostname()
    stage_id: str | None = None
    active_attempt_number: int | None = None
    active_claim_token: str | None = None
    metric_started = started_at()
    try:
        claimed = _claim_task_attempt(
            self, db, job_id, project_id, hostname, attempt_number
        )
        if claimed is None:
            db.rollback()
            return {"status": "already_claimed", "job_id": job_id}
        active_attempt_number, active_claim_token = claimed
        running_job = db.scalar(
            select(Job).where(Job.id == job_id, Job.project_id == project_id)
        )
        if running_job is None:
            raise RuntimeError(f"Claimed job {job_id} is outside project {project_id}")
        if running_job.job_type.value != "MASTERING":
            raise RuntimeError(f"Job {job_id} is not a mastering command")
        record_job_started(running_job.job_type.value)
        require_running_job(
            db, job_id, project_id, active_attempt_number, active_claim_token
        )
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

        job_row = db.execute(
            text(
                """
                SELECT j.id, j.mix_id, j.parameters, a.storage_path
                FROM jobs j
                JOIN mixes m ON m.id = j.mix_id AND m.project_id = j.project_id
                JOIN media_assets a ON a.id = m.media_asset_id AND a.project_id = j.project_id
                WHERE j.id = :id AND j.project_id = :project_id
                """
            ),
            {"id": job_id, "project_id": project_id},
        ).fetchone()
        if job_row is None:
            raise RuntimeError(f"Mastering job {job_id} was not found in its project")

        source_key = job_row.storage_path
        if not source_key.startswith(f"projects/{project_id}/"):
            raise RuntimeError(
                "Mastering source artifact is outside the owning project"
            )
        source_path = StorageService(STORAGE_ROOT).object_path(source_key)
        parameters = (
            job_row.parameters
            if isinstance(job_row.parameters, dict)
            else json.loads(job_row.parameters or "{}")
        )
        settings = MasterSettings(
            target_lufs=float(parameters.get("target_lufs", -9.0)),
            true_peak_dbtp=float(parameters.get("true_peak_dbtp", -1.0)),
            target_lra=float(parameters.get("target_lra", 7.0)),
            eq_settings=parameters.get("eq_settings") or {},
            compressor_settings=parameters.get("compressor_settings") or {},
            project_id=project_id,
            storage_root=Path(STORAGE_ROOT),
            algorithm_version=str(parameters.get("algorithm_version", "v1")),
        )
        stage = StageRun(
            id=str(uuid.uuid4()),
            job_id=job_id,
            stage_name="master_mix",
            stage_version=settings.algorithm_version,
            status=StageStatus.RUNNING,
            progress_percent=5.0,
        )
        stage_id = stage.id
        db.add(stage)

        def progress_tracker(percent: float, stage_name: str) -> None:
            require_running_job(
                db, job_id, project_id, active_attempt_number, active_claim_token
            )
            updated = db.execute(
                text(
                    "UPDATE jobs SET current_stage = :stage, progress_percent = :pct "
                    "WHERE id = :id AND project_id = :project_id AND status = 'RUNNING'"
                ),
                {
                    "id": job_id,
                    "project_id": project_id,
                    "stage": stage_name,
                    "pct": percent,
                },
            )
            if updated.rowcount != 1:
                raise JobStopped(f"Job {job_id} is no longer running")
            progress_job = db.scalar(
                select(Job).where(Job.id == job_id, Job.project_id == project_id)
            )
            if progress_job is None:
                raise JobStopped(f"Job {job_id} is outside project {project_id}")
            progress_event = record_job_event(
                db,
                progress_job,
                "update",
                {
                    "job_id": job_id,
                    "status": JobStatus.RUNNING.value,
                    "progress_percent": percent,
                    "current_stage": stage_name,
                },
            )
            db.commit()
            publish_event(project_id, job_id, event_notification(progress_event))

        progress_tracker(5.0, "Mastering")
        require_running_job(
            db, job_id, project_id, active_attempt_number, active_claim_token
        )
        result = run_master_mix_stage(source_path, settings)
        require_running_job(
            db, job_id, project_id, active_attempt_number, active_claim_token
        )
        # Persist the visible stage result only in the same commit that wins
        # the fenced terminal transition.  The immutable bytes may already
        # exist, but no user can download them without this attachment.
        progress_tracker(95.0, "Mastered")
        require_running_job(
            db, job_id, project_id, active_attempt_number, active_claim_token
        )
        stage = db.get(StageRun, stage_id)
        if stage is None:
            raise RuntimeError(f"Mastering stage for job {job_id} was not persisted")
        stage.status = StageStatus.COMPLETED
        stage.progress_percent = 100.0
        stage.finished_at = datetime.now(timezone.utc)
        stage.stage_output = json.dumps(
            {
                "artifact_key": result.artifact_key,
                "integrated_lufs": result.integrated_lufs,
                "true_peak_dbtp": result.true_peak_dbtp,
                "algorithm_version": result.algorithm_version,
            }
        )
        mastered_key = result.artifact_key
        mastered_artifact = StageArtifact(
            role="mastered",
            key=mastered_key,
            sha256=mastered_key.rsplit("/", 1)[-1],
            algorithm_version=result.algorithm_version,
            media_type="audio/wav",
            byte_length=StorageService(STORAGE_ROOT).object_size(mastered_key),
        )
        persist_artifact_record(
            db,
            project_id=project_id,
            mix_id=job_row.mix_id,
            artifact=mastered_artifact,
            key=mastered_key,
            report={
                "integrated_lufs": result.integrated_lufs,
                "true_peak_dbtp": result.true_peak_dbtp,
            },
        )

        if not complete_job_attempt(
            db, job_id, project_id, hostname, active_attempt_number, active_claim_token
        ):
            db.rollback()
            return {"status": "cancelled", "job_id": job_id}
        advance_batch_after_terminal_job(db, job_id, project_id)
        terminal_event = latest_job_event(db, job_id, project_id)
        db.commit()
        publish_event(project_id, job_id, event_notification(terminal_event))
        record_job_finished("MASTERING", metric_started, "succeeded")
        return {
            "status": "ok",
            "job_id": job_id,
            "master": {
                "artifact_key": result.artifact_key,
                "integrated_lufs": result.integrated_lufs,
                "true_peak_dbtp": result.true_peak_dbtp,
                "algorithm_version": result.algorithm_version,
            },
        }
    except AttemptLeaseUnavailable as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=exc.countdown, max_retries=None)
    except JobStopped:
        db.rollback()
        # The cancellation/reclaim winner owns terminal bookkeeping. A worker
        # that just lost its lease must not write a misleading stage failure
        # after its JobAttempt has been fenced out.
        return {"status": "cancelled", "job_id": job_id}
    except Exception as exc:
        db.rollback()
        record_job_finished("MASTERING", metric_started, "failed")
        if not transition_job_and_attempt(
            db,
            job_id,
            project_id,
            hostname,
            JobStatus.FAILED,
            str(exc),
            active_attempt_number,
            active_claim_token,
        ):
            db.rollback()
            return {"status": "cancelled", "job_id": job_id}
        if stage_id is not None:
            stage = db.get(StageRun, stage_id)
            if stage is not None:
                stage.status = StageStatus.FAILED
                stage.error_message = str(exc)
                stage.finished_at = datetime.now(timezone.utc)
        advance_batch_after_terminal_job(db, job_id, project_id)
        terminal_event = latest_job_event(db, job_id, project_id)
        db.commit()
        publish_event(project_id, job_id, event_notification(terminal_event))
        raise
    finally:
        db.close()


@celery_app.task(name="tasks.cleanup_expired_uploads")
def cleanup_expired_uploads() -> dict[str, int]:
    """Run trusted global upload reconciliation and expiry cleanup on a schedule."""
    db = SessionLocal()
    try:
        storage = StorageService(STORAGE_ROOT)
        reconciled = reconcile_pending_upload_promotions(db, storage)
        expired = cleanup_expired_uploads_global(db, storage)
        return {"reconciled": reconciled, "expired": expired}
    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.run_analysis_pipeline", max_retries=None)
def run_analysis_pipeline(
    self, job_id: str, project_id: str, attempt_number: int | None = None
):
    """
    Execute the real bounded-memory audio analysis, fingerprinting & transition detection pipeline.
    """
    db = SessionLocal()
    hostname = socket.gethostname()
    metric_started = started_at()
    metric_job_type = "ANALYSIS"
    active_attempt_number: int | None = None
    active_claim_token: str | None = None
    try:
        # A broker message is at-least-once.  The conditional claim lets only
        # one worker begin, including after a dispatcher restart/redelivery.
        claimed = _claim_task_attempt(
            self, db, job_id, project_id, hostname, attempt_number
        )
        if claimed is None:
            db.rollback()
            return {"status": "already_claimed", "job_id": job_id}
        active_attempt_number, active_claim_token = claimed
        running_job = db.scalar(
            select(Job).where(Job.id == job_id, Job.project_id == project_id)
        )
        if running_job is None:
            raise RuntimeError(f"Claimed job {job_id} is outside project {project_id}")
        metric_job_type = running_job.job_type.value
        record_job_started(running_job.job_type.value)
        require_running_job(
            db, job_id, project_id, active_attempt_number, active_claim_token
        )
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
                SELECT j.id, j.mix_id, m.media_asset_id, a.storage_path, a.duration_seconds,
                       a.original_filename, a.sha256_hash, a.file_size_bytes, a.mime_type
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
        if not storage_rel_path.startswith(f"projects/{project_id}/"):
            raise RuntimeError("Analysis source artifact is outside the owning project")
        audio_abs_path = StorageService(STORAGE_ROOT).object_path(storage_rel_path)

        def progress_tracker(pct: float, stage_name: str):
            require_running_job(
                db, job_id, project_id, active_attempt_number, active_claim_token
            )
            progress_result = db.execute(
                text(
                    "UPDATE jobs SET current_stage = :stage, progress_percent = :pct WHERE id = :id AND project_id = :project_id AND status = 'RUNNING'"
                ),
                {
                    "id": job_id,
                    "project_id": project_id,
                    "stage": stage_name,
                    "pct": pct,
                },
            )
            if progress_result.rowcount != 1:
                raise JobStopped(f"Job {job_id} is no longer running")
            progress_job = db.scalar(
                select(Job).where(Job.id == job_id, Job.project_id == project_id)
            )
            if progress_job is None:
                raise JobStopped(f"Job {job_id} is outside project {project_id}")
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
        require_running_job(
            db, job_id, project_id, active_attempt_number, active_claim_token
        )
        orchestrator = AudioAnalysisOrchestrator(audio_abs_path, duration_seconds)
        analysis_data = orchestrator.execute_pipeline(
            progress_callback=progress_tracker
        )

        # Compute immutable payloads first.  They are not user-visible until
        # the atomic publication below attaches their database records.
        require_running_job(
            db, job_id, project_id, active_attempt_number, active_claim_token
        )
        source_artifact = StageArtifact(
            role="source",
            key=storage_rel_path,
            sha256=job_row.sha256_hash,
            algorithm_version="v1",
            media_type=job_row.mime_type or "application/octet-stream",
            byte_length=int(job_row.file_size_bytes),
        )
        progress_tracker(82.0, "Generating metadata report")
        tagged_mix = tag_mix(
            audio_abs_path, source_artifact, job_row.original_filename, "v1"
        )
        require_running_job(
            db, job_id, project_id, active_attempt_number, active_claim_token
        )
        metadata_key = owner_scoped_artifact_key(
            project_id, tagged_mix.metadata_artifact.key
        )
        persist_immutable_payload(STORAGE_ROOT, metadata_key, tagged_mix.payload)
        progress_tracker(90.0, "Generating waveform artifact")
        waveform = generate_waveform(
            audio_abs_path, points=2048, algorithm_version="v1"
        )
        require_running_job(
            db, job_id, project_id, active_attempt_number, active_claim_token
        )
        waveform_key = owner_scoped_artifact_key(project_id, waveform.key)
        persist_immutable_payload(STORAGE_ROOT, waveform_key, waveform.payload)

        progress_tracker(95.0, "Publishing analysis")
        require_running_job(
            db, job_id, project_id, active_attempt_number, active_claim_token
        )
        terminal_event = publish_analysis_results(
            db,
            job_id=job_id,
            project_id=project_id,
            hostname=hostname,
            attempt_number=active_attempt_number,
            claim_token=active_claim_token,
            mix_id=mix_id,
            media_asset_id=media_asset_id,
            analysis_data=analysis_data,
            source_artifact=source_artifact,
            source_key=storage_rel_path,
            tagged_mix=tagged_mix,
            metadata_key=metadata_key,
            waveform=waveform,
            waveform_key=waveform_key,
        )
        db.commit()
        publish_event(project_id, job_id, event_notification(terminal_event))
        record_job_finished(metric_job_type, metric_started, "succeeded")

        return {"status": "ok", "job_id": job_id, "analysis": analysis_data}

    except AttemptLeaseUnavailable as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=exc.countdown, max_retries=None)
    except JobStopped:
        db.rollback()
        return {"status": "cancelled", "job_id": job_id}
    except Exception as e:
        db.rollback()
        record_job_finished(metric_job_type, metric_started, "failed")
        error_str = str(e)
        if not transition_job_and_attempt(
            db,
            job_id,
            project_id,
            hostname,
            JobStatus.FAILED,
            error_str,
            active_attempt_number,
            active_claim_token,
        ):
            db.rollback()
            return {"status": "cancelled", "job_id": job_id}
        advance_batch_after_terminal_job(db, job_id, project_id)
        terminal_event = latest_job_event(db, job_id, project_id)
        db.commit()
        publish_event(project_id, job_id, event_notification(terminal_event))
        raise
    finally:
        db.close()
