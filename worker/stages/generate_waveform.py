"""Versioned waveform artifact stage.

File IO lives here: stream deterministic peaks from the source through
``worker.dsp.waveforms.compute_waveform`` and persist one canonical JSON
payload to ``dest``. Repeats over the same source bytes reuse the same
artifact identity, mirroring ``api.app.services.artifacts.artifact_key``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf

from worker.dsp.waveforms import (
    WAVEFORM_ALGORITHM_VERSION,
    WAVEFORM_ARTIFACT_ROLE,
    compute_waveform,
)


@dataclass(frozen=True)
class WaveformResult:
    """Immutable waveform artifact identity for one source."""

    artifact_key: str
    sha256: str
    algorithm_version: str
    media_type: str
    byte_length: int
    points: int
    sample_rate: int
    duration_seconds: float
    peaks: tuple[float, ...]


def waveform_artifact_key(
    source_sha256: str,
    algorithm_version: str = WAVEFORM_ALGORITHM_VERSION,
) -> str:
    """Return the immutable storage key for a waveform payload."""
    if not source_sha256:
        raise ValueError("source_sha256 must not be empty")
    if not algorithm_version:
        raise ValueError("algorithm_version must not be empty")
    return f"artifacts/{WAVEFORM_ARTIFACT_ROLE}/{algorithm_version}/{source_sha256}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def generate_waveform(
    source: Path,
    dest: Path,
    points: int = 2048,
    algorithm_version: str = WAVEFORM_ALGORITHM_VERSION,
) -> WaveformResult:
    """Create the canonical waveform JSON for ``source`` and persist it to ``dest``."""
    if not algorithm_version:
        raise ValueError("algorithm_version must not be empty")
    src = Path(source)
    dst = Path(dest)
    if not src.is_file():
        raise FileNotFoundError("waveform source artifact does not exist")

    peaks = compute_waveform(src, points)
    info = sf.info(str(src))
    duration_seconds = round(float(info.frames / info.samplerate), 6)
    payload = json.dumps(
        {
            "duration_seconds": duration_seconds,
            "peaks": peaks,
            "points": points,
            "sample_rate": int(info.samplerate),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(payload)
    return WaveformResult(
        artifact_key=waveform_artifact_key(_sha256(src), algorithm_version),
        sha256=hashlib.sha256(payload).hexdigest(),
        algorithm_version=algorithm_version,
        media_type="application/json",
        byte_length=len(payload),
        points=points,
        sample_rate=int(info.samplerate),
        duration_seconds=duration_seconds,
        peaks=tuple(peaks),
    )


__all__ = ["WaveformResult", "generate_waveform", "waveform_artifact_key"]
