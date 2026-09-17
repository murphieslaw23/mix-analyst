"""Job event streaming: durable DB replay first, Redis live tail second.

Every stored row is emitted with an `id: <sequence>` frame so browsers can
resume with Last-Event-ID and never miss a terminal event. The Redis tail
is a latency optimization only — if the broker is unreachable the stream
simply ends after the replay instead of hanging.
"""

import json
from collections.abc import AsyncGenerator, Callable

import redis
import redis.asyncio as aioredis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from ..config import settings
from .job_events_store import get_events_since

TERMINAL_STATUSES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})


def _payload_status(raw: str) -> str | None:
    try:
        status = json.loads(raw).get("status")
    except (ValueError, AttributeError):
        return None
    return status if isinstance(status, str) else None


def publish_terminal_event(
    job_id: str,
    status: str,
    *,
    progress_percent: float = 0.0,
    current_stage: str | None = None,
    error_message: str | None = None,
) -> None:
    """Best-effort synchronous fan-out (API paths have no async Redis)."""
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.publish(
            f"job:{job_id}:events",
            json.dumps(
                {
                    "job_id": job_id,
                    "status": status,
                    "progress_percent": progress_percent,
                    "current_stage": current_stage,
                    "error_message": error_message,
                }
            ),
        )
        client.close()
    except (RedisError, OSError):
        pass


async def stream_job_events(
    job_id: str,
    *,
    session_factory: Callable[[], Session] | None = None,
    last_event_id: int = 0,
) -> AsyncGenerator[str, None]:
    """Replay stored events after `last_event_id`, then tail Redis live."""
    yield (
        f"event: connect\ndata: {json.dumps({'job_id': job_id, 'message': 'Connected to event stream'})}\n\n"
    )

    replayed_terminal = False
    if session_factory is not None:
        db = session_factory()
        try:
            for row in get_events_since(db, job_id, last_event_id):
                yield f"id: {row.sequence}\nevent: update\ndata: {row.payload}\n\n"
                if _payload_status(row.payload) in TERMINAL_STATUSES:
                    replayed_terminal = True
                    yield (
                        f"id: {row.sequence}\nevent: close\n"
                        f"data: {json.dumps({'job_id': job_id, 'status': _payload_status(row.payload)})}\n\n"
                    )
        finally:
            db.close()

    if replayed_terminal:
        return

    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        channel = f"job:{job_id}:events"
        await pubsub.subscribe(channel)
    except (RedisError, OSError):
        return

    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg:
                raw_data = msg["data"]
                yield f"event: update\ndata: {raw_data}\n\n"
                terminal_status = _payload_status(raw_data)
                if terminal_status in TERMINAL_STATUSES:
                    yield f"event: close\ndata: {json.dumps({'job_id': job_id, 'status': terminal_status})}\n\n"
                    break
            else:
                yield ": keepalive\n\n"
    finally:
        try:
            await pubsub.unsubscribe(channel)
        except (RedisError, OSError):
            pass
        try:
            await client.aclose()
        except (RedisError, OSError):
            pass
