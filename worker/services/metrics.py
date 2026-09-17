"""Privacy-safe in-memory operational metrics for the worker.

Stage helpers delegate to a local thread-safe store that enforces the same
tag allowlist as the API: media filenames, user content, and storage keys
must never become metric labels.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Mapping

ALLOWED_TAGS: set[str] = {"job_type", "status", "stage", "queue"}

STAGE_LATENCY_GAUGE: str = "worker_stage_latency_seconds"
STAGE_FAILURE_COUNTER: str = "worker_stage_failures_total"

_counters: dict[str, float] = {}
_gauges: dict[str, float] = {}
_lock = threading.Lock()


def _validate_tags(tags: Mapping[str, str]) -> dict[str, str]:
    """Validate tag keys against the allowlist and return a plain dict."""
    extra: set[str] = set(tags) - ALLOWED_TAGS
    if extra:
        raise ValueError(f"unsupported metric tag(s): {sorted(extra)}")
    cleaned: dict[str, str] = {}
    for key, value in tags.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError("metric tag keys and values must be strings")
        cleaned[key] = value
    return cleaned


def _canonical_key(name: str, tags: Mapping[str, str]) -> str:
    """Build a deterministic series key from a name and sorted tags."""
    if not tags:
        return name
    parts: list[str] = [f'{key}="{tags[key]}"' for key in sorted(tags)]
    return f"{name}{{{','.join(parts)}}}"


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not name:
        raise ValueError("metric name must be a non-empty string")
    return name


def record_counter(
    name: str, value: int = 1, tags: Mapping[str, str] | None = None
) -> None:
    """Increment a worker-side in-memory counter for allowlisted tags."""
    _validate_name(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("counter value must be an int")
    cleaned: dict[str, str] = _validate_tags(tags or {})
    key: str = _canonical_key(name, cleaned)
    with _lock:
        _counters[key] = _counters.get(key, 0) + value


def record_gauge(
    name: str, value: float, tags: Mapping[str, str] | None = None
) -> None:
    """Set a worker-side in-memory gauge for allowlisted tags."""
    _validate_name(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("gauge value must be a number")
    cleaned: dict[str, str] = _validate_tags(tags or {})
    key: str = _canonical_key(name, cleaned)
    with _lock:
        _gauges[key] = float(value)


def record_stage_latency(stage: str, seconds: float, job_type: str) -> None:
    """Record per-stage latency using only allowlisted tags."""
    if not isinstance(stage, str) or not stage:
        raise ValueError("stage must be a non-empty string")
    if not isinstance(job_type, str) or not job_type:
        raise ValueError("job_type must be a non-empty string")
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or not math.isfinite(float(seconds))
        or float(seconds) < 0
    ):
        raise ValueError("seconds must be a finite non-negative number")
    record_gauge(
        STAGE_LATENCY_GAUGE,
        float(seconds),
        {"stage": stage, "job_type": job_type},
    )


def record_stage_failure(stage: str, job_type: str) -> None:
    """Count per-stage failures using only allowlisted tags."""
    if not isinstance(stage, str) or not stage:
        raise ValueError("stage must be a non-empty string")
    if not isinstance(job_type, str) or not job_type:
        raise ValueError("job_type must be a non-empty string")
    record_counter(STAGE_FAILURE_COUNTER, 1, {"stage": stage, "job_type": job_type})


def snapshot() -> dict[str, dict[str, float]]:
    """Return a point-in-time copy of worker counters and gauges."""
    with _lock:
        return {"counters": dict(_counters), "gauges": dict(_gauges)}


def reset() -> None:
    """Clear all recorded worker series. Intended for tests."""
    with _lock:
        _counters.clear()
        _gauges.clear()
