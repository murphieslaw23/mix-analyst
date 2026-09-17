"""Persistent batch endpoints: fan out analysis jobs and read aggregates."""

from typing import Annotated

from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.app.api.deps import get_current_principal, require_api_key
from api.app.config import settings
from api.app.db.session import get_db
from api.app.models.batch import Batch
from api.app.models.job import Job, JobStatus
from api.app.schemas.auth import CurrentPrincipal
from api.app.schemas.batch import BatchCreateRequest, BatchItemOut, BatchOut
from api.app.services.batches import create_batch, recompute_batch_status

router = APIRouter()
celery_client = Celery("mix_analyst_client", broker=settings.celery_broker_url)


def _to_batch_out(db: Session, batch: Batch) -> BatchOut:
    children: list[Job] = (
        db.query(Job).filter(Job.batch_id == batch.id).order_by(Job.created_at).all()
    )
    queued_count = sum(1 for job in children if job.status == JobStatus.QUEUED)
    running_count = sum(1 for job in children if job.status == JobStatus.RUNNING)
    completed_count = sum(1 for job in children if job.status == JobStatus.SUCCEEDED)
    failed_count = sum(1 for job in children if job.status == JobStatus.FAILED)
    cancelled_count = sum(1 for job in children if job.status == JobStatus.CANCELLED)
    items: list[BatchItemOut] = [
        BatchItemOut(
            job_id=job.id,
            mix_id=job.mix_id,
            status=job.status.value
            if isinstance(job.status, JobStatus)
            else str(job.status),
        )
        for job in children
    ]
    return BatchOut(
        id=batch.id,
        project_id=batch.project_id,
        status=batch.status,
        total_count=batch.total_count,
        queued_count=queued_count,
        running_count=running_count,
        completed_count=completed_count,
        failed_count=failed_count,
        cancelled_count=cancelled_count,
        items=items,
        created_at=batch.created_at,
    )


@router.post("/batches", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def post_batch(
    req: BatchCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    _auth: Annotated[None, Depends(require_api_key)],
) -> BatchOut:
    """Fan out one ANALYSIS child job per owned mix (bounded parallelism)."""
    try:

        def _send(task_name: str, args: list, task_id: str, queue: str) -> str:
            return celery_client.send_task(
                task_name, args=args, task_id=task_id, queue=queue
            ).id

        batch = create_batch(
            db,
            project_id=principal.project_id,
            mix_ids=req.mix_ids,
            sender=_send,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return _to_batch_out(db, batch)


@router.get("/batches/{batch_id}", response_model=BatchOut)
def get_batch(
    batch_id: str,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> BatchOut:
    """Read one owned batch aggregate (project-scoped, 404 for foreign)."""
    batch = (
        db.query(Batch)
        .filter(Batch.id == batch_id, Batch.project_id == principal.project_id)
        .first()
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found"
        )
    recompute_batch_status(db, batch)
    return _to_batch_out(db, batch)
