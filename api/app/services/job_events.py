"""Replayable SSE delivery for durable project-scoped job events."""

import asyncio
import json
from collections.abc import AsyncGenerator

import redis
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models.job import Job, JobAttempt, JobStatus
from ..models.job_event import JobEvent
from .metrics import record_counter


TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}


def job_event_channel(project_id: str, job_id: str) -> str:
    """Namespace transient wakeups by their authenticated project and job."""
    return f"project:{project_id}:job:{job_id}:events"


def event_notification(event: JobEvent) -> dict:
    """Build the transient Redis wakeup only after the event transaction commits."""
    return {
        "sequence": event.sequence,
        "event_type": event.event_type,
        "attempt_number": event.attempt_number,
        "payload": event.payload,
    }


def publish_event(project_id: str, job_id: str, payload: dict) -> None:
    """Publish a post-commit wakeup; durable storage remains the event source."""
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        client.publish(job_event_channel(project_id, job_id), json.dumps(payload))
    except Exception as exc:
        print(f"Failed to publish Redis event: {exc}")
    finally:
        client.close()


def encode_sse_event(event: JobEvent) -> str:
    """Encode a durable event with its replay cursor before its data."""
    payload = {**event.payload, "attempt_number": event.attempt_number}
    return f"id: {event.sequence}\nevent: {event.event_type}\ndata: {json.dumps(payload)}\n\n"


def is_terminal_event(event: JobEvent) -> bool:
    return event.payload.get("status") in TERMINAL_STATUSES


async def stream_job_events(
    db: Session,
    project_id: str,
    job_id: str,
    last_event_id: int = 0,
) -> AsyncGenerator[str, None]:
    """Replay committed rows after a cursor, then reliably tail later rows.

    Redis is a wakeup optimization, never the event source. A database read
    occurs after subscription and on each wakeup or timeout, so a missed
    Pub/Sub message cannot make a committed event disappear.
    """
    record_counter("sse.reconnect")
    if last_event_id > 0:
        record_counter("sse.replay")
    last_sequence = last_event_id
    terminal_delivered = False

    def pending_events() -> list[JobEvent]:
        db.expire_all()
        return list(
            db.scalars(
                select(JobEvent)
                .where(
                    JobEvent.project_id == project_id,
                    JobEvent.job_id == job_id,
                    JobEvent.sequence > last_sequence,
                )
                .order_by(JobEvent.sequence)
            )
        )

    def current_attempt_number() -> int | None:
        return db.scalar(
            select(JobAttempt.attempt_number)
            .where(JobAttempt.job_id == job_id)
            .order_by(JobAttempt.attempt_number.desc())
            .limit(1)
        )

    def replay_pending() -> list[str]:
        nonlocal last_sequence, terminal_delivered
        encoded = []
        for event in pending_events():
            if event.sequence <= last_sequence:
                continue
            last_sequence = event.sequence
            encoded.append(encode_sse_event(event))
            # A terminal row from a prior attempt remains replayable, but it
            # cannot close a stream whose job has been retried.
            if is_terminal_event(event) and event.attempt_number == current_attempt_number():
                terminal_delivered = True
        return encoded

    def job_is_terminal() -> bool:
        status = db.scalar(
            select(Job.status).where(Job.id == job_id, Job.project_id == project_id)
        )
        return status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED)

    for encoded in replay_pending():
        yield encoded
    if terminal_delivered or (job_is_terminal() and current_attempt_number() is not None):
        return

    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    subscribed = False
    try:
        try:
            await pubsub.subscribe(job_event_channel(project_id, job_id))
            subscribed = True
        except Exception:
            # Persisted rows remain replayable even when the optional Redis
            # acceleration layer is unavailable.
            await client.aclose()

        # Close the replay/subscription race with another ordered DB read.
        for encoded in replay_pending():
            yield encoded
        if terminal_delivered or (job_is_terminal() and current_attempt_number() is not None):
            return

        while True:
            if subscribed:
                await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            else:
                await asyncio.sleep(1.0)
            encoded_events = replay_pending()
            for encoded in encoded_events:
                yield encoded
            if terminal_delivered or (job_is_terminal() and current_attempt_number() is not None):
                return
            if not encoded_events:
                yield ": keepalive\n\n"
    finally:
        if subscribed:
            await pubsub.unsubscribe(job_event_channel(project_id, job_id))
            await client.aclose()
