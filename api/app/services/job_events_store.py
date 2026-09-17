"""Durable, ordered job events.

The database is the system of record: every stage boundary and terminal
outcome commits a sequenced row, so SSE can replay missed events after a
reconnect (Last-Event-ID) instead of relying on Redis alone.
"""

import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.job_event import JobEvent


def next_sequence(db: Session, job_id: str) -> int:
    current = (
        db.query(func.max(JobEvent.sequence)).filter(JobEvent.job_id == job_id).scalar()
    )
    return int(current or 0) + 1


def record_job_event(
    db: Session, job_id: str, event_type: str, payload: dict[str, Any] | None = None
) -> JobEvent:
    """Append the next sequenced event for a job (retries one sequence race)."""
    for _ in range(2):
        event = JobEvent(
            job_id=job_id,
            sequence=next_sequence(db, job_id),
            event_type=event_type,
            payload=json.dumps(payload or {}),
        )
        db.add(event)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(event)
        return event
    raise RuntimeError(f"Could not sequence job event for {job_id}")


def get_events_since(
    db: Session, job_id: str, after_sequence: int = 0
) -> list[JobEvent]:
    """Ordered replay slice for SSE reconnection."""
    return (
        db.query(JobEvent)
        .filter(JobEvent.job_id == job_id, JobEvent.sequence > after_sequence)
        .order_by(JobEvent.sequence.asc())
        .all()
    )
