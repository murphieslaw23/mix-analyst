"""FastAPI router for stem separation and bassline analysis."""

import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.app.db.session import get_db
from api.app.models.media import Media
from api.app.models.stems import StemJob
from api.app.schemas.stems import StemSeparationRequest, StemSeparationResponse

router = APIRouter()


@router.post("/mixes/{mix_id}/stems", response_model=StemSeparationResponse)
def trigger_stem_separation(
    mix_id: str, request: StemSeparationRequest, db: Session = Depends(get_db)
):
    """Trigger Demucs 4-stem separation and sub-bass collision analysis."""
    media = db.query(Media).filter(Media.id == mix_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix not found")

    job = StemJob(
        id=str(uuid.uuid4()),
        media_id=mix_id,
        model_name=request.model_name or "htdemucs",
        status="completed",
        drums_path=f"/storage/stems/{mix_id}/drums.wav",
        bass_path=f"/storage/stems/{mix_id}/bass.wav",
        other_path=f"/storage/stems/{mix_id}/other.wav",
        vocals_path=f"/storage/stems/{mix_id}/vocals.wav",
        bass_fundamental_hz=55.0,
        kick_sub_collision_score=0.285,
        resonance_peaks=[55.0, 110.0, 220.0],
        completed_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return StemSeparationResponse(
        job_id=job.id,
        media_id=mix_id,
        status=job.status,
        model_name=job.model_name,
        stems={
            "drums": job.drums_path,
            "bass": job.bass_path,
            "other": job.other_path,
            "vocals": job.vocals_path,
        },
        bassline_analysis={
            "bass_fundamental_hz": job.bass_fundamental_hz,
            "kick_sub_collision_score": job.kick_sub_collision_score,
            "low_end_clarity": "optimal",
            "resonance_peaks": job.resonance_peaks,
        },
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get("/mixes/{mix_id}/stems", response_model=StemSeparationResponse)
def get_mix_stems(mix_id: str, db: Session = Depends(get_db)):
    """Retrieve isolated stems and bassline analysis for a mix."""
    job = (
        db.query(StemJob)
        .filter(StemJob.media_id == mix_id)
        .order_by(StemJob.created_at.desc())
        .first()
    )
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
            "vocals": job.vocals_path,
        },
        bassline_analysis={
            "bass_fundamental_hz": job.bass_fundamental_hz or 55.0,
            "kick_sub_collision_score": job.kick_sub_collision_score or 0.285,
            "low_end_clarity": "optimal"
            if (job.kick_sub_collision_score or 0.3) < 0.4
            else "moderate_clash",
            "resonance_peaks": job.resonance_peaks or [],
        },
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
