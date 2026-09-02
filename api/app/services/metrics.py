"""Small, bounded in-process metrics registry.

Metrics deliberately have a much narrower data contract than application
events.  In particular, no caller may attach an identifier, filename, storage
key, token, or other caller supplied value as a label.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from threading import Lock


ALLOWED_TAGS = frozenset({"job_type", "status", "stage", "queue"})
ALLOWED_TAG_VALUES = {
    "job_type": frozenset({"ANALYSIS", "FINGERPRINT", "RESTORATION", "MASTERING", "EXPORT"}),
    "status": frozenset({"queued", "running", "succeeded", "failed", "cancelled", "rejected", "pending"}),
    "stage": frozenset({"analysis", "mastering", "restoration", "export", "metadata", "waveform", "upload"}),
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


def _validated_tags(tags: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    unsupported = set(tags) - ALLOWED_TAGS
    if unsupported:
        raise ValueError("unsupported metric tag")
    for name, value in tags.items():
        if not isinstance(value, str) or value not in ALLOWED_TAG_VALUES[name]:
            raise ValueError("unsupported metric tag value")
    return tuple(sorted(tags.items()))


def record_counter(name: str, value: int = 1, tags: Mapping[str, str] = {}) -> None:
    """Record an approved counter without accepting customer data as labels."""
    if name not in ALLOWED_COUNTERS:
        raise ValueError("unsupported metric name")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("metric value must be a non-negative integer")
    key = (name, _validated_tags(tags))
    with _lock:
        _counters[key] += value


def counter_samples() -> list[tuple[str, int, dict[str, str]]]:
    """Return a copy suitable for rendering by the authenticated API only."""
    with _lock:
        return [(name, value, dict(tags)) for (name, tags), value in sorted(_counters.items())]
