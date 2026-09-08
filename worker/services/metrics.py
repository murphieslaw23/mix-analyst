"""Worker-side, privacy-safe operational counters."""

from __future__ import annotations

import time

from api.app.services.metrics import record_counter

JOB_STAGES = {
    "ANALYSIS": "analysis",
    "FINGERPRINT": "analysis",
    "RESTORATION": "restoration",
    "MASTERING": "mastering",
    "EXPORT": "export",
}
JOB_QUEUES = {
    "ANALYSIS": "analysis-cpu",
    "FINGERPRINT": "analysis-cpu",
    "RESTORATION": "dsp-heavy",
    "MASTERING": "dsp-heavy",
    "EXPORT": "exports",
}


def started_at() -> float:
    return time.monotonic()


def record_job_started(job_type: str) -> None:
    record_counter(
        "job.started",
        tags={"job_type": job_type, "queue": JOB_QUEUES[job_type], "status": "running"},
    )


def record_job_finished(job_type: str, start_time: float, status: str) -> None:
    tags = {"job_type": job_type, "stage": JOB_STAGES[job_type], "status": status}
    elapsed_ms = max(0, int((time.monotonic() - start_time) * 1000))
    record_counter("job.stage.duration_ms", elapsed_ms, tags)
    if status == "failed":
        record_counter("job.failed", tags=tags)
