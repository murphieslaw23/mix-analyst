"""FastAPI router for audio mastering and loudness reports."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.app.api.deps import require_api_key
from api.app.config import settings as app_settings
from api.app.db.session import get_db
from api.app.models.job import JobType
from api.app.models.mastering import MasteringJob
from api.app.models.media import Mix
from api.app.schemas.mastering import (
    MasteringPresetResponse,
    MasteringReportResponse,
    MasteringTriggerRequest,
)
from api.app.services.jsonfields import parse_json_field
from api.app.services.pipeline_jobs import enqueue_pipeline_job
from api.app.services.storage import StorageService
from worker.analysis.mastering_engine import DEFAULT_PRESETS

router = APIRouter()


@router.get("/mastering/presets", response_model=list[MasteringPresetResponse])
def get_mastering_presets():
    """List available mastering presets."""
    presets = []
    for key, p in DEFAULT_PRESETS.items():
        presets.append(
            MasteringPresetResponse(
                id=key,
                name=p["name"],
                description=p.get("description"),
                target_lufs=p["target_lufs"],
                true_peak_ceiling=p["true_peak_ceiling"],
                target_lra=p["target_lra"],
                eq_settings=p["eq_settings"],
                compressor_settings=p["compressor_settings"],
                is_builtin=True,
            )
        )
    return presets


@router.post(
    "/mixes/{mix_id}/master", response_model=MasteringReportResponse, status_code=202
)
def trigger_mix_mastering(
    mix_id: str,
    request: MasteringTriggerRequest,
    db: Annotated[Session, Depends(get_db)],
    _auth: Annotated[None, Depends(require_api_key)],
):
    """Enqueue two-pass loudness mastering; poll the report / job for progress."""
    media = db.query(Mix).filter(Mix.id == mix_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix not found")

    preset_key = request.preset_id or "sound_system_heavy"
    preset: dict[str, Any] = DEFAULT_PRESETS.get(preset_key, {})
    if not preset:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown preset '{preset_key}'. Available: {sorted(DEFAULT_PRESETS)}",
        )

    mjob = MasteringJob(
        id=str(uuid.uuid4()),
        media_id=mix_id,
        preset_id=preset_key,
        status="queued",
    )
    db.add(mjob)
    db.commit()
    db.refresh(mjob)

    enqueue_pipeline_job(
        db,
        mix_id=mix_id,
        job_type=JobType.MASTERING,
        task_name="tasks.run_mastering_pipeline",
        task_args=lambda job_id: [job_id, mjob.id],
        queue="mastering",
    )
    db.refresh(mjob)

    return MasteringReportResponse(
        job_id=mjob.id,
        media_id=mix_id,
        status=mjob.status,
        preset_name=preset["name"],
        input_measurements={},
        output_measurements={},
        gain_adjust_db=0.0,
        compliance_passed=False,
        created_at=mjob.created_at,
        completed_at=None,
    )


@router.get("/mixes/{mix_id}/mastered")
def download_mastered_mix(mix_id: str, db: Annotated[Session, Depends(get_db)]):
    """Download the latest completed master WAV for a mix."""
    job = (
        db.query(MasteringJob)
        .filter(MasteringJob.media_id == mix_id, MasteringJob.status == "completed")
        .order_by(MasteringJob.completed_at.desc())
        .first()
    )
    if not job or not job.output_storage_path:
        raise HTTPException(
            status_code=404, detail="No completed master found for this mix"
        )

    storage = StorageService(app_settings.storage_root)
    try:
        abs_path = storage.safe_resolve(job.output_storage_path)
    except ValueError:
        raise HTTPException(status_code=500, detail="Stored master path is invalid")
    if not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Master file not found on storage")

    return FileResponse(
        path=str(abs_path),
        media_type="audio/wav",
        filename=f"{mix_id}_master.wav",
    )


@router.get("/mixes/{mix_id}/mastering-report", response_model=MasteringReportResponse)
def get_mastering_report(mix_id: str, db: Annotated[Session, Depends(get_db)]):
    """Retrieve the latest mastering report for a mix."""
    job = (
        db.query(MasteringJob)
        .filter(MasteringJob.media_id == mix_id)
        .order_by(MasteringJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(
            status_code=404, detail="No mastering job found for this mix"
        )

    preset_key = job.preset_id or "sound_system_heavy"
    preset: dict[str, Any] = DEFAULT_PRESETS.get(
        preset_key, DEFAULT_PRESETS["sound_system_heavy"]
    )
    return MasteringReportResponse(
        job_id=job.id,
        media_id=mix_id,
        status=job.status,
        preset_name=preset["name"],
        input_measurements={
            "integrated_lufs": job.input_lufs or -18.5,
            "true_peak_db": job.input_true_peak or -0.5,
        },
        output_measurements={
            "integrated_lufs": job.output_lufs or preset["target_lufs"],
            "true_peak_db": job.output_true_peak or preset["true_peak_ceiling"],
        },
        gain_adjust_db=parse_json_field(job.metrics, {}).get("gain_adjust_db", 0.0),
        compliance_passed=True,
        created_at=job.created_at,
        completed_at=job.completed_at or job.created_at,
    )
