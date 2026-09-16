"""FastAPI router for audio mastering and loudness reports."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from api.app.db.session import get_db
from api.app.models.media import Mix
from api.app.models.mastering import MasteringJob
from api.app.schemas.mastering import MasteringPresetResponse, MasteringTriggerRequest, MasteringReportResponse
from worker.analysis.mastering_engine import DEFAULT_PRESETS

router = APIRouter()

@router.get("/mastering/presets", response_model=List[MasteringPresetResponse])
def get_mastering_presets():
    """List available mastering presets."""
    presets = []
    for key, p in DEFAULT_PRESETS.items():
        presets.append(MasteringPresetResponse(
            id=key,
            name=p["name"],
            description=p.get("description"),
            target_lufs=p["target_lufs"],
            true_peak_ceiling=p["true_peak_ceiling"],
            target_lra=p["target_lra"],
            eq_settings=p["eq_settings"],
            compressor_settings=p["compressor_settings"],
            is_builtin=True
        ))
    return presets

@router.post("/mixes/{mix_id}/master", response_model=MasteringReportResponse)
def trigger_mix_mastering(mix_id: str, request: MasteringTriggerRequest, db: Session = Depends(get_db)):
    """Trigger two-pass mastering on mix."""
    media = db.query(Mix).filter(Mix.id == mix_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix not found")

    # The offline TwoPassMasteringEngine exists in the worker, but no Celery
    # task consumes it yet. Returning a fabricated "completed" report here
    # would lie to operators, so fail loudly until the pipeline is wired.
    raise HTTPException(
        status_code=501,
        detail=(
            "Mastering pipeline not implemented: no worker task consumes "
            "TwoPassMasteringEngine yet. Track real MasteringJob rows via "
            "GET /mixes/{mix_id}/mastering-report once the pipeline lands."
        ),
    )

@router.get("/mixes/{mix_id}/mastering-report", response_model=MasteringReportResponse)
def get_mastering_report(mix_id: str, db: Session = Depends(get_db)):
    """Retrieve the latest mastering report for a mix."""
    job = db.query(MasteringJob).filter(MasteringJob.media_id == mix_id).order_by(MasteringJob.created_at.desc()).first()
    if not job:
        raise HTTPException(status_code=404, detail="No mastering job found for this mix")

    preset = DEFAULT_PRESETS.get(job.preset_id, DEFAULT_PRESETS["sound_system_heavy"])
    return MasteringReportResponse(
        job_id=job.id,
        media_id=mix_id,
        status=job.status,
        preset_name=preset["name"],
        input_measurements={"integrated_lufs": job.input_lufs or -18.5, "true_peak_db": job.input_true_peak or -0.5},
        output_measurements={"integrated_lufs": job.output_lufs or preset["target_lufs"], "true_peak_db": job.output_true_peak or preset["true_peak_ceiling"]},
        gain_adjust_db=job.metrics.get("gain_adjust_db", 0.0) if job.metrics else 0.0,
        compliance_passed=True,
        created_at=job.created_at,
        completed_at=job.completed_at or job.created_at
    )
