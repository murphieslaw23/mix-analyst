"""FastAPI router for stem separation and bassline analysis."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.app.api.deps import require_api_key
from api.app.db.session import get_db
from api.app.models.job import JobType
from api.app.models.media import Mix
from api.app.models.stems import StemJob
from api.app.schemas.stems import StemSeparationRequest, StemSeparationResponse
from api.app.services.pipeline_jobs import enqueue_pipeline_job

router = APIRouter()


@router.post(
    "/mixes/{mix_id}/stems", response_model=StemSeparationResponse, status_code=202
)
def trigger_stem_separation(
    mix_id: str,
    request: StemSeparationRequest,
    db: Annotated[Session, Depends(get_db)],
    _auth: Annotated[None, Depends(require_api_key)],
):
    """Enqueue Demucs 4-stem separation; fails clearly if Demucs is absent.

    Demucs + torch are an optional worker extra (excluded from the base
    images to stay RPi-viable). Without them the job ends FAILED with an
    actionable message instead of fake results.
    """
    media = db.query(Mix).filter(Mix.id == mix_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix not found")

    sjob = StemJob(
        id=str(uuid.uuid4()),
        media_id=mix_id,
        model_name=request.model_name or "htdemucs",
        status="queued",
    )
    db.add(sjob)
    db.commit()
    db.refresh(sjob)

    enqueue_pipeline_job(
        db,
        mix_id=mix_id,
        job_type=JobType.STEM_SEPARATION,
        task_name="tasks.run_stem_separation",
        task_args=lambda job_id: [job_id, sjob.id],
        queue="stems",
    )
    db.refresh(sjob)

    return StemSeparationResponse(
        job_id=sjob.id,
        media_id=mix_id,
        status=sjob.status,
        model_name=sjob.model_name,
        stems={},
        bassline_analysis={},
        created_at=sjob.created_at,
        completed_at=None,
    )


@router.get("/mixes/{mix_id}/stems", response_model=StemSeparationResponse)
def get_mix_stems(mix_id: str, db: Annotated[Session, Depends(get_db)]):
    """Retrieve isolated stems and bassline analysis for a mix."""
    job = (
        db.query(StemJob)
        .filter(StemJob.media_id == mix_id)
        .order_by(StemJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No stems found for this mix")

    if job.status == "completed":
        bassline: dict = {
            "bass_fundamental_hz": job.bass_fundamental_hz,
            "kick_sub_collision_score": job.kick_sub_collision_score,
            "low_end_clarity": "optimal"
            if (job.kick_sub_collision_score or 0.3) < 0.4
            else "moderate_clash",
            "resonance_peaks": job.resonance_peaks or [],
        }
    else:
        bassline = {}

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
        bassline_analysis=bassline,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
