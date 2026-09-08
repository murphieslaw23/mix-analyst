"""Authenticated batch creation, aggregate reads, and failed-item recovery."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models.batch import Batch
from ...schemas.auth import CurrentPrincipal
from ...schemas.batch import BatchCreateRequest, BatchOut, BatchRetryRequest
from ...services.batches import create_batch, recompute_batch_status, retry_batch_items
from ..deps import get_current_principal

router = APIRouter()


def _require_owned_batch(
    db: Session, principal: CurrentPrincipal, batch_id: str
) -> Batch:
    batch = db.scalar(
        select(Batch).where(
            Batch.id == batch_id, Batch.project_id == principal.project_id
        )
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found"
        )
    return batch


@router.post("/batches", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create_owned_batch(
    request: BatchCreateRequest,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    try:
        batch = create_batch(db, principal, request)
        db.commit()
    except (PermissionError, ValueError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
            if isinstance(exc, PermissionError)
            else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None
    db.refresh(batch)
    return batch


@router.get("/batches/{batch_id}", response_model=BatchOut)
def get_owned_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    batch = _require_owned_batch(db, principal, batch_id)
    recompute_batch_status(db, batch.id)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/batches/{batch_id}/retry", response_model=BatchOut)
def retry_failed_batch_items(
    batch_id: str,
    request: BatchRetryRequest,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    batch = _require_owned_batch(db, principal, batch_id)
    try:
        retry_batch_items(db, batch, request.job_ids)
        db.commit()
    except (PermissionError, ValueError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
            if isinstance(exc, PermissionError)
            else status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    db.refresh(batch)
    return batch
