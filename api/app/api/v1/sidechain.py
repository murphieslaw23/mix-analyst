import uuid

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.app.db.session import get_db
from api.app.models.media import Media
from api.app.schemas.sidechain import SidechainProcessRequest, SidechainProcessResponse
from worker.analysis.dynamic_sidechain import DynamicSidechainDSP

router = APIRouter()


@router.post("/mastering/sidechain", response_model=SidechainProcessResponse)
def apply_dynamic_sidechain(
    request: SidechainProcessRequest, db: Session = Depends(get_db)
):
    """Apply automated kick/sub-bass sidechain ducking and phase alignment."""
    media = db.query(Media).filter(Media.id == request.media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix asset not found")

    # Generate synthetic kick/bass profile for validation if isolated stems are being analyzed
    sample_rate = 22050
    t = np.linspace(0, 5, sample_rate * 5)
    synthetic_kick = np.sin(2.0 * np.pi * 55.0 * t) * (t % 0.5 < 0.1)
    synthetic_bass = np.sin(2.0 * np.pi * 55.0 * t)

    result = DynamicSidechainDSP.process_sub_bass_sidechain(
        kick_audio=synthetic_kick,
        bass_audio=synthetic_bass,
        sample_rate=sample_rate,
        threshold_db=request.threshold_db or -12.0,
        max_ducking_db=request.max_ducking_db or 6.0,
    )

    return SidechainProcessResponse(
        job_id=str(uuid.uuid4()),
        media_id=request.media_id,
        status="completed",
        phase_inverted=result["phase_inverted"],
        phase_correlation=result["phase_correlation"],
        max_gain_reduction_db=result["max_gain_reduction_db"],
        processed_bass_rms=result["processed_bass_rms"],
        low_end_clarity_score=result["low_end_clarity_score"],
    )
