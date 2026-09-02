"""Create the baseline Mix Analyst schema.

Revision ID: 20260902_01
Revises:
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


upload_status = sa.Enum("PENDING", "UPLOADING", "COMPLETED", "FAILED", "ABORTED", name="uploadstatus")
job_type = sa.Enum("ANALYSIS", "FINGERPRINT", "RESTORATION", "MASTERING", "EXPORT", name="jobtype")
job_status = sa.Enum("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED", name="jobstatus")
stage_status = sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED", name="stagestatus")


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("sample_rate", sa.BigInteger(), nullable=False),
        sa.Column("channels", sa.BigInteger(), nullable=False),
        sa.Column("codec", sa.String(length=50), nullable=False),
        sa.Column("bit_rate", sa.BigInteger(), nullable=True),
        sa.Column("format_name", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_path"),
    )
    op.create_index("ix_media_assets_sha256_hash", "media_assets", ["sha256_hash"])

    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("total_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("bytes_received", sa.BigInteger(), nullable=False),
        sa.Column("chunk_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=True),
        sa.Column("temp_path", sa.String(length=512), nullable=False),
        sa.Column("status", upload_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mixes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("artist", sa.String(length=255), nullable=True),
        sa.Column("media_asset_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mastering_presets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("target_lufs", sa.Float(), nullable=True),
        sa.Column("true_peak_ceiling", sa.Float(), nullable=True),
        sa.Column("target_lra", sa.Float(), nullable=True),
        sa.Column("eq_settings", sa.JSON(), nullable=True),
        sa.Column("compressor_settings", sa.JSON(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mastering_presets_id", "mastering_presets", ["id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mix_id", sa.String(length=36), nullable=False),
        sa.Column("job_type", job_type, nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("progress_percent", sa.Float(), nullable=False),
        sa.Column("current_stage", sa.String(length=100), nullable=True),
        sa.Column("celery_task_id", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["mix_id"], ["mixes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_mix_id", "jobs", ["mix_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_celery_task_id", "jobs", ["celery_task_id"])

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mix_id", sa.String(length=36), nullable=False),
        sa.Column("media_asset_id", sa.String(length=36), nullable=False),
        sa.Column("primary_bpm", sa.Float(), nullable=False),
        sa.Column("bpm_confidence", sa.Float(), nullable=False),
        sa.Column("bpm_candidates", sa.Text(), nullable=True),
        sa.Column("detected_key", sa.String(length=50), nullable=False),
        sa.Column("camelot_code", sa.String(length=10), nullable=False),
        sa.Column("key_confidence", sa.Float(), nullable=False),
        sa.Column("integrated_lufs", sa.Float(), nullable=False),
        sa.Column("loudness_range_lra", sa.Float(), nullable=False),
        sa.Column("true_peak_db", sa.Float(), nullable=False),
        sa.Column("spectral_summary", sa.Text(), nullable=True),
        sa.Column("quality_findings", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"]),
        sa.ForeignKeyConstraint(["mix_id"], ["mixes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mix_id"),
    )
    op.create_index("ix_analysis_results_mix_id", "analysis_results", ["mix_id"])

    op.create_table(
        "track_segments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mix_id", sa.String(length=36), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("start_time_seconds", sa.Float(), nullable=False),
        sa.Column("end_time_seconds", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mix_id"], ["mixes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_track_segments_mix_id", "track_segments", ["mix_id"])

    op.create_table(
        "transition_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mix_id", sa.String(length=36), nullable=False),
        sa.Column("transition_index", sa.Integer(), nullable=False),
        sa.Column("start_time_seconds", sa.Float(), nullable=False),
        sa.Column("end_time_seconds", sa.Float(), nullable=False),
        sa.Column("cue_in_time", sa.Float(), nullable=False),
        sa.Column("cue_out_time", sa.Float(), nullable=False),
        sa.Column("transition_type", sa.String(length=50), nullable=False),
        sa.Column("energy_delta", sa.Float(), nullable=False),
        sa.Column("tempo_shift_bpm", sa.Float(), nullable=False),
        sa.Column("camelot_compatibility", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mix_id"], ["mixes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transition_events_mix_id", "transition_events", ["mix_id"])

    op.create_table(
        "mastering_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("media_id", sa.String(), nullable=False),
        sa.Column("preset_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("input_lufs", sa.Float(), nullable=True),
        sa.Column("input_true_peak", sa.Float(), nullable=True),
        sa.Column("input_lra", sa.Float(), nullable=True),
        sa.Column("output_lufs", sa.Float(), nullable=True),
        sa.Column("output_true_peak", sa.Float(), nullable=True),
        sa.Column("output_lra", sa.Float(), nullable=True),
        sa.Column("output_storage_path", sa.String(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["media_id"], ["media_assets.id"]),
        sa.ForeignKeyConstraint(["preset_id"], ["mastering_presets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mastering_jobs_id", "mastering_jobs", ["id"])
    op.create_index("ix_mastering_jobs_media_id", "mastering_jobs", ["media_id"])

    op.create_table(
        "broadcast_syncs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("media_id", sa.String(), nullable=False),
        sa.Column("station_id", sa.String(), nullable=True),
        sa.Column("playlist_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("azuracast_media_id", sa.String(), nullable=True),
        sa.Column("cue_markers_synced", sa.Integer(), nullable=True),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["media_id"], ["media_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_broadcast_syncs_id", "broadcast_syncs", ["id"])
    op.create_index("ix_broadcast_syncs_media_id", "broadcast_syncs", ["media_id"])

    op.create_table(
        "stem_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("media_id", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("drums_path", sa.String(), nullable=True),
        sa.Column("bass_path", sa.String(), nullable=True),
        sa.Column("other_path", sa.String(), nullable=True),
        sa.Column("vocals_path", sa.String(), nullable=True),
        sa.Column("bass_fundamental_hz", sa.Float(), nullable=True),
        sa.Column("kick_sub_collision_score", sa.Float(), nullable=True),
        sa.Column("resonance_peaks", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["media_id"], ["media_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stem_jobs_id", "stem_jobs", ["id"])
    op.create_index("ix_stem_jobs_media_id", "stem_jobs", ["media_id"])

    op.create_table(
        "job_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("worker_hostname", sa.String(length=255), nullable=True),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_attempts_job_id", "job_attempts", ["job_id"])

    op.create_table(
        "stage_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("stage_name", sa.String(length=100), nullable=False),
        sa.Column("stage_version", sa.String(length=50), nullable=False),
        sa.Column("param_hash", sa.String(length=64), nullable=True),
        sa.Column("status", stage_status, nullable=False),
        sa.Column("progress_percent", sa.Float(), nullable=False),
        sa.Column("stage_output", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stage_runs_job_id", "stage_runs", ["job_id"])

    op.create_table(
        "track_matches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("segment_id", sa.String(length=36), nullable=False),
        sa.Column("mix_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("artist", sa.String(length=255), nullable=False),
        sa.Column("album", sa.String(length=255), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("isrc", sa.String(length=50), nullable=True),
        sa.Column("acoustid_id", sa.String(length=100), nullable=True),
        sa.Column("musicbrainz_recording_id", sa.String(length=100), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mix_id"], ["mixes.id"]),
        sa.ForeignKeyConstraint(["segment_id"], ["track_segments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("segment_id"),
    )
    op.create_index("ix_track_matches_segment_id", "track_matches", ["segment_id"])
    op.create_index("ix_track_matches_mix_id", "track_matches", ["mix_id"])


def downgrade() -> None:
    op.drop_index("ix_track_matches_mix_id", table_name="track_matches")
    op.drop_index("ix_track_matches_segment_id", table_name="track_matches")
    op.drop_table("track_matches")
    op.drop_index("ix_stage_runs_job_id", table_name="stage_runs")
    op.drop_table("stage_runs")
    op.drop_index("ix_job_attempts_job_id", table_name="job_attempts")
    op.drop_table("job_attempts")
    op.drop_index("ix_stem_jobs_media_id", table_name="stem_jobs")
    op.drop_index("ix_stem_jobs_id", table_name="stem_jobs")
    op.drop_table("stem_jobs")
    op.drop_index("ix_broadcast_syncs_media_id", table_name="broadcast_syncs")
    op.drop_index("ix_broadcast_syncs_id", table_name="broadcast_syncs")
    op.drop_table("broadcast_syncs")
    op.drop_index("ix_mastering_jobs_media_id", table_name="mastering_jobs")
    op.drop_index("ix_mastering_jobs_id", table_name="mastering_jobs")
    op.drop_table("mastering_jobs")
    op.drop_index("ix_transition_events_mix_id", table_name="transition_events")
    op.drop_table("transition_events")
    op.drop_index("ix_track_segments_mix_id", table_name="track_segments")
    op.drop_table("track_segments")
    op.drop_index("ix_analysis_results_mix_id", table_name="analysis_results")
    op.drop_table("analysis_results")
    op.drop_index("ix_jobs_celery_task_id", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_mix_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_mastering_presets_id", table_name="mastering_presets")
    op.drop_table("mastering_presets")
    op.drop_table("mixes")
    op.drop_table("upload_sessions")
    op.drop_index("ix_media_assets_sha256_hash", table_name="media_assets")
    op.drop_table("media_assets")
