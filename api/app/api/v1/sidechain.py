import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.app.api.deps import require_api_key
from api.app.config import settings as app_settings
from api.app.db.session import get_db
from api.app.models.job import JobType
from api.app.models.media import Mix
from api.app.models.sidechain import SidechainJob
from api.app.models.stems import StemJob
from api.app.schemas.sidechain import (
    SidechainProcessRequest,
    SidechainProcessResponse,
    SidechainReportResponse,
)
from api.app.services.pipeline_jobs import enqueue_pipeline_job
from api.app.services.storage import StorageService

router = APIRouter()


def _latest_usable_stems(db: Session, mix_id: str) -> StemJob | None:
    """Newest completed stem job whose drums/bass files exist on storage."""
    storage = StorageService(app_settings.storage_root)
    jobs = (
        db.query(StemJob)
        .filter(StemJob.media_id == mix_id, StemJob.status == "completed")
        .order_by(StemJob.completed_at.desc())
        .all()
    )
    for job in jobs:
        try:
            drums = storage.safe_resolve(job.drums_path) if job.drums_path else None
            bass = storage.safe_resolve(job.bass_path) if job.bass_path else None
        except ValueError:
            continue
        if drums and bass and drums.is_file() and bass.is_file():
            return job
    return None


@router.post(
    "/mastering/sidechain", response_model=SidechainProcessResponse, status_code=202
)
def apply_dynamic_sidechain(
    request: SidechainProcessRequest,
    db: Annotated[Session, Depends(get_db)],
    _auth: Annotated[None, Depends(require_api_key)],
):
    """Enqueue kick/sub sidechain ducking on real separated stems (409 otherwise)."""
    media = db.query(Mix).filter(Mix.id == request.media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix asset not found")

    if not _latest_usable_stems(db, request.media_id):
        raise HTTPException(
            status_code=409,
            detail="Sidechain requires a completed stem separation with drums/bass files on storage",
        )

    scj = SidechainJob(
        id=str(uuid.uuid4()),
        media_id=request.media_id,
        status="queued",
        threshold_db=request.threshold_db
        if request.threshold_db is not None
        else -12.0,
        max_ducking_db=request.max_ducking_db
        if request.max_ducking_db is not None
        else 6.0,
    )
    db.add(scj)
    db.commit()
    db.refresh(scj)

    enqueue_pipeline_job(
        db,
        mix_id=request.media_id,
        job_type=JobType.SIDECHAIN,
        task_name="tasks.run_sidechain",
        task_args=lambda job_id: [job_id, scj.id],
        queue="mastering",
    )
    db.refresh(scj)

    return SidechainProcessResponse(
        job_id=scj.id,
        media_id=request.media_id,
        status=scj.status,
        phase_inverted=False,
        phase_correlation=0.0,
        max_gain_reduction_db=0.0,
        processed_bass_rms=0.0,
        low_end_clarity_score=0.0,
    )


@router.get("/mixes/{mix_id}/sidechain", response_model=SidechainReportResponse)
def get_sidechain_report(mix_id: str, db: Annotated[Session, Depends(get_db)]):
    """Retrieve the latest sidechain result for a mix."""
    job = (
        db.query(SidechainJob)
        .filter(SidechainJob.media_id == mix_id)
        .order_by(SidechainJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(
            status_code=404, detail="No sidechain job found for this mix"
        )

    return SidechainReportResponse(
        job_id=job.id,
        media_id=mix_id,
        status=job.status,
        threshold_db=job.threshold_db,
        max_ducking_db=job.max_ducking_db,
        phase_inverted=job.phase_inverted,
        phase_correlation=job.phase_correlation,
        max_gain_reduction_db=job.max_gain_reduction_db,
        processed_bass_rms=job.processed_bass_rms,
        low_end_clarity_score=job.low_end_clarity_score,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
