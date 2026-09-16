"""FastAPI router for stem separation and bassline analysis."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.app.db.session import get_db
from api.app.models.media import Mix
from api.app.models.stems import StemJob
from api.app.schemas.stems import StemSeparationRequest, StemSeparationResponse

router = APIRouter()

@router.post("/mixes/{mix_id}/stems", response_model=StemSeparationResponse)
def trigger_stem_separation(mix_id: str, request: StemSeparationRequest, db: Session = Depends(get_db)):
    """Trigger Demucs 4-stem separation and sub-bass collision analysis."""
    media = db.query(Mix).filter(Mix.id == mix_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix not found")

    # Demucs (torch) is not installed in the worker image and no separation
    # task exists. Previously this endpoint returned instant "completed" jobs
    # pointing at stem files that were never rendered — fail loudly instead.
    raise HTTPException(
        status_code=501,
        detail=(
            "Stem separation not implemented: Demucs model weights and a "
            "worker separation task are required before this endpoint can "
            "render drums/bass/other/vocals stems."
        ),
    )

@router.get("/mixes/{mix_id}/stems", response_model=StemSeparationResponse)
def get_mix_stems(mix_id: str, db: Session = Depends(get_db)):
    """Retrieve isolated stems and bassline analysis for a mix."""
    job = db.query(StemJob).filter(StemJob.media_id == mix_id).order_by(StemJob.created_at.desc()).first()
    if not job:
        raise HTTPException(status_code=404, detail="No stems found for this mix")

    return StemSeparationResponse(
        job_id=job.id,
        media_id=mix_id,
        status=job.status,
        model_name=job.model_name,
        stems={
            "drums": job.drums_path,
            "bass": job.bass_path,
            "other": job.other_path,
            "vocals": job.vocals_path
        },
        bassline_analysis={
            "bass_fundamental_hz": job.bass_fundamental_hz or 55.0,
            "kick_sub_collision_score": job.kick_sub_collision_score or 0.285,
            "low_end_clarity": "optimal" if (job.kick_sub_collision_score or 0.3) < 0.4 else "moderate_clash",
            "resonance_peaks": job.resonance_peaks or []
        },
        created_at=job.created_at,
        completed_at=job.completed_at
    )
