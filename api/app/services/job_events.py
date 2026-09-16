import json
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from ..config import settings


async def stream_job_events(job_id: str) -> AsyncGenerator[str, None]:
    """Stream real-time Server-Sent Events (SSE) for a specific job from Redis pub/sub."""
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    channel = f"job:{job_id}:events"
    await pubsub.subscribe(channel)

    try:
        # Initial connect ping
        yield f"event: connect\ndata: {json.dumps({'job_id': job_id, 'message': 'Connected to event stream'})}\n\n"

        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg:
                raw_data = msg["data"]
                yield f"event: update\ndata: {raw_data}\n\n"
                try:
                    terminal_status = json.loads(raw_data).get("status")
                except (ValueError, AttributeError):
                    terminal_status = None
                if terminal_status in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                    yield f"event: close\ndata: {json.dumps({'job_id': job_id, 'status': terminal_status})}\n\n"
                    break
            else:
                # Periodic keepalive comment
                yield ": keepalive\n\n"
    finally:
        await pubsub.unsubscribe(channel)
        await client.aclose()
