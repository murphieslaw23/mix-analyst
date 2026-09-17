"""Pure loudness-mastering math for the worker runtime.

This module performs no file IO and never touches storage: it computes the
deterministic gain/ceiling values a stage needs and the content-addressed
artifact-key shape shared with ``api.app.services.artifacts``. Streaming the
audio and measuring loudness belong to ``worker.stages.master_mix``, which
adapts the two-pass gain/clip pipeline from ``worker.tasks`` and the
measurement pass from ``worker.analysis.loudness_analyzer``.
"""

from __future__ import annotations

from dataclasses import dataclass

MASTERING_ALGORITHM_VERSION = "twopass-mastering/1.0.0"
MASTER_ARTIFACT_ROLE = "master"


@dataclass(frozen=True)
class MasterSettings:
    """Stable settings for one immutable mastering execution."""

    target_lufs: float = -9.0
    true_peak_dbtp: float = -1.0

    def __post_init__(self) -> None:
        if not -36.0 <= self.target_lufs <= -3.0:
            raise ValueError("target_lufs must be between -36 and -3")
        if not -12.0 <= self.true_peak_dbtp <= 0.0:
            raise ValueError("true_peak_dbtp must be between -12 and 0")


@dataclass(frozen=True)
class MasterResult:
    """Immutable report for one mastered artifact."""

    artifact_key: str
    integrated_lufs: float
    true_peak_dbtp: float
    algorithm_version: str = MASTERING_ALGORITHM_VERSION


def db_to_linear(gain_db: float) -> float:
    """Convert a decibel gain value to a linear amplitude multiplier."""
    return 10.0 ** (gain_db / 20.0)


def compute_master_gain(input_lufs: float, settings: MasterSettings) -> float:
    """Return the pass-one gain (dB) moving measured input to target loudness."""
    return settings.target_lufs - input_lufs


def peak_ceiling_linear(settings: MasterSettings) -> float:
    """Return the true-peak ceiling as a linear amplitude limit."""
    return db_to_linear(settings.true_peak_dbtp)


def master_artifact_key(
    content_sha256: str,
    algorithm_version: str = MASTERING_ALGORITHM_VERSION,
) -> str:
    """Return the immutable storage key for a mastered artifact payload."""
    if not content_sha256:
        raise ValueError("content_sha256 must not be empty")
    if not algorithm_version:
        raise ValueError("algorithm_version must not be empty")
    return f"artifacts/{MASTER_ARTIFACT_ROLE}/{algorithm_version}/{content_sha256}"


__all__ = [
    "MASTERING_ALGORITHM_VERSION",
    "MASTER_ARTIFACT_ROLE",
    "MasterResult",
    "MasterSettings",
    "compute_master_gain",
    "db_to_linear",
    "master_artifact_key",
    "peak_ceiling_linear",
]
