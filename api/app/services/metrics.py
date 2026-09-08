"""Bounded metrics registry with Redis aggregation across API and workers.

Metrics deliberately have a much narrower data contract than application
events.  In particular, no caller may attach an identifier, filename, storage
key, token, or other caller supplied value as a label.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from threading import Lock

import redis

from ..config import settings

ALLOWED_TAGS = frozenset({"job_type", "status", "stage", "queue"})
ALLOWED_TAG_VALUES = {
    "job_type": frozenset(
        {"ANALYSIS", "FINGERPRINT", "RESTORATION", "MASTERING", "EXPORT"}
    ),
    "status": frozenset(
        {"queued", "running", "succeeded", "failed", "cancelled", "rejected", "pending"}
    ),
    "stage": frozenset(
        {
            "analysis",
            "mastering",
            "restoration",
            "export",
            "metadata",
            "waveform",
            "upload",
        }
    ),
    "queue": frozenset({"analysis-cpu", "dsp-heavy", "metadata-network", "exports"}),
}
ALLOWED_COUNTERS = frozenset(
    {
        "job.enqueued",
        "job.started",
        "job.stage.duration_ms",
        "job.failed",
        "upload.rejected",
        "sse.reconnect",
        "sse.replay",
    }
)

_counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)
_lock = Lock()
_COUNTER_HASH_KEY = "mix-analyst:metrics:v1:counters"


def _validated_tags(tags: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    unsupported = set(tags) - ALLOWED_TAGS
    if unsupported:
        raise ValueError("unsupported metric tag")
    for name, value in tags.items():
        if not isinstance(value, str) or value not in ALLOWED_TAG_VALUES[name]:
            raise ValueError("unsupported metric tag value")
    return tuple(sorted(tags.items()))


def record_counter(name: str, value: int = 1, tags: Mapping[str, str] = {}) -> None:
    """Record an approved counter without accepting customer data as labels.

    Redis is the deployment's shared broker and aggregation backend, so every
    API worker and Celery process contributes to one bounded hash. Telemetry
    must not make uploads or DSP fail: if Redis is temporarily unavailable the
    process retains only its own fallback sample and a scrape reports that the
    shared backend is unavailable.
    """
    if name not in ALLOWED_COUNTERS:
        raise ValueError("unsupported metric name")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("metric value must be a non-negative integer")
    key = (name, _validated_tags(tags))
    try:
        client = _metrics_redis_client()
        try:
            _flush_local_counters(client)
            client.hincrby(_COUNTER_HASH_KEY, _metric_field(*key), value)
        finally:
            client.close()
    except Exception:  # noqa: BLE001 - retain process-local counters during Redis outages.
        with _lock:
            _counters[key] += value


def counter_samples() -> list[tuple[str, int, dict[str, str]]]:
    """Return process-local fallback samples when shared aggregation is down."""
    with _lock:
        return [
            (name, value, dict(tags))
            for (name, tags), value in sorted(_counters.items())
        ]


def shared_counter_samples() -> tuple[list[tuple[str, int, dict[str, str]]], bool]:
    """Read only valid, fixed identities from the shared aggregation hash."""
    try:
        client = _metrics_redis_client()
        try:
            _flush_local_counters(client)
            stored = client.hgetall(_COUNTER_HASH_KEY)
        finally:
            client.close()
    except Exception:  # noqa: BLE001 - return the safe local fallback during Redis outages.
        return counter_samples(), False

    samples = []
    for field, raw_value in stored.items():
        decoded = _metric_from_field(field)
        if decoded is None:
            continue
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            name, tags = decoded
            samples.append((name, value, dict(tags)))
    return sorted(
        samples, key=lambda sample: (sample[0], tuple(sorted(sample[2].items())))
    ), True


def _flush_local_counters(client) -> None:
    """Drain fallback samples into Redis without dropping unsent increments.

    Each successful ``HINCRBY`` is removed individually. If the connection
    fails part-way through the drain, all not-yet-confirmed counters remain in
    process memory for the next recovery attempt. A response lost after Redis
    accepted an increment may over-count on retry, but it can never silently
    lose operational evidence, which is the safe failure direction for this
    best-effort telemetry path.
    """
    with _lock:
        pending = list(_counters.items())
    for key, pending_value in pending:
        if pending_value <= 0:
            continue
        client.hincrby(_COUNTER_HASH_KEY, _metric_field(*key), pending_value)
        with _lock:
            current = _counters.get(key, 0)
            # New failures for this key may have arrived while Redis was being
            # updated; remove only the snapshot we just confirmed.
            remaining = current - pending_value
            if remaining > 0:
                _counters[key] = remaining
            else:
                _counters.pop(key, None)


def _metrics_redis_client():
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )


def _metric_field(name: str, tags: tuple[tuple[str, str], ...]) -> str:
    """Encode only a prevalidated identity; no request value reaches Redis."""
    return json.dumps([name, list(tags)], separators=(",", ":"))


def _metric_from_field(field: str) -> tuple[str, tuple[tuple[str, str], ...]] | None:
    """Treat unexpected Redis contents as untrusted and never expose them."""
    try:
        name, raw_tags = json.loads(field)
        if not isinstance(name, str) or not isinstance(raw_tags, list):
            return None
        tags = dict(raw_tags)
        if len(tags) != len(raw_tags) or not all(isinstance(key, str) for key in tags):
            return None
        if name not in ALLOWED_COUNTERS:
            return None
        return name, _validated_tags(tags)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
