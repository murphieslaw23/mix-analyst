"""Operational metrics endpoint (operator-only in locked mode)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ...services.metrics import snapshot
from ..deps import require_api_key

router = APIRouter()


@router.get("/metrics")
def get_metrics(
    _auth: Annotated[None, Depends(require_api_key)],
) -> dict[str, dict[str, float]]:
    """Return the current in-memory metrics snapshot as JSON."""
    return snapshot()
