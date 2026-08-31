import json
import redis.asyncio as aioredis
from typing import AsyncGenerator
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
                    parsed = json.loads(raw_data)
                    if parsed.get("status") in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                        yield f"event: close\ndata: {json.dumps({'job_id': job_id, 'status': parsed.get('status')})}\n\n"
                        break
                except Exception:
                    pass
            else:
                # Periodic keepalive comment
                yield ": keepalive\n\n"
    finally:
        await pubsub.unsubscribe(channel)
        await client.aclose()
