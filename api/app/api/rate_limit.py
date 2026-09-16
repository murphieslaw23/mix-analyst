"""Fixed-window rate limiting for write methods.

Reads stay unlimited (radio metadata + PWA polling use-case). Chunk uploads
(PATCH) are exempt — a single 4 GB mix legitimately bursts hundreds of
requests; per-session offsets and auth already guard that path.

Redis-backed with a transparent in-memory fallback when the broker is down.
"""

import time

import redis
from fastapi import Request, Response
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from ..config import settings

LIMITED_METHODS = {"POST", "PUT", "DELETE"}

_memory_buckets: dict[str, list[float]] = {}


def _redis_client():
    return redis.from_url(
        settings.redis_url, socket_connect_timeout=1, socket_timeout=1
    )


def check_rate_limit(key: str, limit: int, window_s: int) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds). Pure logic, unit-testable."""
    now = time.time()
    try:
        client = _redis_client()
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, window_s)
        if count <= limit:
            return True, 0
        ttl = client.ttl(key)
        return False, max(int(ttl), 0)
    except (RedisError, OSError):
        bucket = _memory_buckets.setdefault(key, [])
        cutoff = now - window_s
        bucket[:] = [t for t in bucket if t > cutoff]
        if len(_memory_buckets) > 10000:
            # Bound memory: drop buckets that are already fully expired.
            for dead in [
                k for k, v in _memory_buckets.items() if not v or v[-1] <= cutoff
            ]:
                del _memory_buckets[dead]
        if len(bucket) >= limit:
            return False, max(int(bucket[0] + window_s - now) + 1, 0)
        bucket.append(now)
        return True, 0


def client_key(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return f"rl:{host}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        limit = settings.rate_limit_per_minute
        if limit > 0 and request.method in LIMITED_METHODS:
            allowed, retry_after = check_rate_limit(client_key(request), limit, 60)
            if not allowed:
                return Response(
                    content='{"detail":"Rate limit exceeded"}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(retry_after)},
                )
        return await call_next(request)
