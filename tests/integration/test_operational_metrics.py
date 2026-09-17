"""Privacy-safe operational metrics tests. No DB needed."""

from __future__ import annotations

import re

import pytest

import api.app.services.metrics as api_metrics
import worker.services.metrics as worker_metrics
from api.app.services.metrics import record_counter


def test_record_counter_increments_and_snapshot_exposes_it() -> None:
    api_metrics.reset()
    record_counter(
        "job.completed",
        tags={"job_type": "ANALYSIS", "status": "SUCCEEDED"},
    )
    record_counter(
        "job.completed",
        value=2,
        tags={"job_type": "ANALYSIS", "status": "SUCCEEDED"},
    )
    snap: dict[str, dict[str, float]] = api_metrics.snapshot()
    assert "counters" in snap and "gauges" in snap
    matching: dict[str, float] = {
        key: value
        for key, value in snap["counters"].items()
        if key.startswith("job.completed")
    }
    assert matching, f"expected job.completed series, got: {snap['counters']}"
    assert sum(matching.values()) == 3


def test_metric_tags_do_not_accept_filename_or_user_content() -> None:
    api_metrics.reset()
    with pytest.raises(ValueError):
        record_counter("job.completed", tags={"filename": "private.wav"})
    with pytest.raises(ValueError):
        api_metrics.record_gauge("job.latency", 1.0, tags={"storage_key": "k"})
    snap: dict[str, dict[str, float]] = api_metrics.snapshot()
    blob: str = repr(snap)
    assert "private.wav" not in blob
    assert "filename" not in blob
    assert api_metrics.ALLOWED_TAGS == {"job_type", "status", "stage", "queue"}


def test_worker_stage_helpers_record_allowlisted_tags_only() -> None:
    worker_metrics.reset()
    worker_metrics.record_stage_latency("master_mix", 1.25, "MASTERING")
    worker_metrics.record_stage_failure("master_mix", "MASTERING")
    snap: dict[str, dict[str, float]] = worker_metrics.snapshot()
    assert snap["gauges"], "expected stage latency gauge series"
    assert snap["counters"], "expected stage failure counter series"
    assert worker_metrics.ALLOWED_TAGS == {"job_type", "status", "stage", "queue"}
    with pytest.raises(ValueError):
        worker_metrics.record_counter("x", tags={"filename": "private.wav"})
    keys: list[str] = list(snap["counters"]) + list(snap["gauges"])
    assert any("master_mix" in key for key in keys)
    assert any("MASTERING" in key for key in keys)
    tag_key_pattern = re.compile(r'([A-Za-z_][A-Za-z0-9_]*?)="')
    for key in keys:
        found: set[str] = set(tag_key_pattern.findall(key))
        assert found <= worker_metrics.ALLOWED_TAGS, f"key {key!r} has {found}"
        assert "filename" not in key
    assert "private.wav" not in repr(snap)
