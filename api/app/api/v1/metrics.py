"""Operator-only Prometheus-compatible operational metrics."""

from __future__ import annotations

from datetime import datetime, timezone
from os import environ

import redis
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import settings
from ...db.session import get_db
from ...models.job import Job
from ...models.outbox import OutboxMessage
from ...schemas.auth import CurrentPrincipal
from ...services.metrics import shared_counter_samples
from ..deps import get_current_principal


router = APIRouter()
QUEUES = ("analysis-cpu", "dsp-heavy", "metadata-network", "exports")


def _operator_ids() -> frozenset[str]:
    """Read an explicit server-side allowlist; absence denies every caller."""
    return frozenset(item.strip() for item in environ.get("OPERATOR_USER_IDS", "").split(",") if item.strip())


def require_operator(principal: CurrentPrincipal = Depends(get_current_principal)) -> CurrentPrincipal:
    if principal.user_id not in _operator_ids():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator access required")
    return principal


def _labels(tags: dict[str, str]) -> str:
    if not tags:
        return ""
    return "{" + ",".join(f'{key}="{value}"' for key, value in sorted(tags.items())) + "}"


def _sample(name: str, value: int | float, tags: dict[str, str] | None = None) -> str:
    return f"mix_analyst_{name}{_labels(tags or {})} {value}"


def _queue_depths() -> list[tuple[str, int]]:
    client = redis.from_url(
        settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
    )
    try:
        return [(queue, int(client.llen(queue))) for queue in QUEUES]
    finally:
        client.close()


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics(
    db: Session = Depends(get_db),
    _: CurrentPrincipal = Depends(require_operator),
):
    """Expose aggregate operational state without project or media labels."""
    lines = []
    counter_metrics, shared_metrics_available = shared_counter_samples()
    for name, value, tags in counter_metrics:
        lines.append(_sample(name.replace(".", "_"), value, tags))
    lines.append(_sample("counter_backend_available", int(shared_metrics_available)))

    for job_type, job_status, count in db.execute(
        select(Job.job_type, Job.status, func.count()).group_by(Job.job_type, Job.status)
    ):
        lines.append(
            _sample(
                "jobs",
                int(count),
                {"job_type": job_type.value, "status": job_status.value.lower()},
            )
        )

    oldest_pending = db.scalar(select(func.min(OutboxMessage.created_at)).where(OutboxMessage.delivered_at.is_(None)))
    pending = int(db.scalar(select(func.count()).select_from(OutboxMessage).where(OutboxMessage.delivered_at.is_(None))) or 0)
    lag_seconds = 0
    if oldest_pending is not None:
        if oldest_pending.tzinfo is None:
            oldest_pending = oldest_pending.replace(tzinfo=timezone.utc)
        lag_seconds = max(0, int((datetime.now(timezone.utc) - oldest_pending).total_seconds()))
    lines.append(_sample("outbox_pending", pending, {"status": "pending"}))
    lines.append(_sample("outbox_lag_seconds", lag_seconds, {"status": "pending"}))

    try:
        for queue, depth in _queue_depths():
            lines.append(_sample("queue_depth", depth, {"queue": queue}))
        lines.append(_sample("queue_check_available", 1))
    except Exception:
        lines.append(_sample("queue_check_available", 0))

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
