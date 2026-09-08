"""Authenticated durable commands for the mastering worker stage."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.app.api.deps import get_current_principal, require_owned_mix
from api.app.db.session import get_db
from api.app.schemas.auth import CurrentPrincipal
from api.app.schemas.job import JobCreateRequest, JobOut
from api.app.schemas.mastering import MasteringTriggerRequest
from api.app.services.job_commands import enqueue_job
from api.app.services.mastering_presets import resolve_mastering_parameters

router = APIRouter()


@router.post(
    "/mixes/{mix_id}/master",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_mix_mastering(
    mix_id: str,
    request: MasteringTriggerRequest,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Queue mastering; completion is reported only by the owning worker."""
    mix = require_owned_mix(db, principal, mix_id)
    parameters = resolve_mastering_parameters(
        db,
        principal,
        request.preset_id,
        target_lufs=request.target_lufs,
        true_peak_dbtp=request.true_peak_ceiling,
    )
    job = enqueue_job(
        db,
        principal,
        mix,
        JobCreateRequest(
            job_type="MASTERING",
            parameters=parameters,
        ),
    )
    db.commit()
    db.refresh(job)
    return job
