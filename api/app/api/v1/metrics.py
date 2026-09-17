"""Operational metrics endpoint.

Wiring into ``main.py`` is done separately; this module only defines ``router``.
"""

from __future__ import annotations

from fastapi import APIRouter

from ...services.metrics import snapshot

router = APIRouter()


@router.get("/metrics")
def get_metrics() -> dict[str, dict[str, float]]:
    """Return the current in-memory metrics snapshot as JSON."""
    return snapshot()
