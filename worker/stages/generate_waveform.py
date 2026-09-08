"""Versioned, pure waveform artifact stage."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from worker.dsp.waveforms import extract_peaks


def artifact_key(source_sha256: str, role: str, algorithm_version: str) -> str:
    return f"artifacts/{role}/{algorithm_version}/{source_sha256}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class WaveformArtifact:
    role: str
    key: str
    sha256: str
    algorithm_version: str
    media_type: str
    byte_length: int
    payload: bytes
    points: int
    duration_seconds: float


def generate_waveform(
    source: Path, points: int, algorithm_version: str
) -> WaveformArtifact:
    """Create canonical waveform JSON for a source, without writing storage."""
    if not algorithm_version:
        raise ValueError("algorithm_version must not be empty")
    peaks, sample_rate, duration_seconds = extract_peaks(Path(source), points)
    payload = json.dumps(
        {
            "duration_seconds": duration_seconds,
            "peaks": peaks,
            "points": points,
            "sample_rate": sample_rate,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    source_hash = _sha256(Path(source))
    return WaveformArtifact(
        role="waveform",
        key=artifact_key(source_hash, "waveform", algorithm_version),
        sha256=hashlib.sha256(payload).hexdigest(),
        algorithm_version=algorithm_version,
        media_type="application/json",
        byte_length=len(payload),
        payload=payload,
        points=points,
        duration_seconds=duration_seconds,
    )


__all__ = ["WaveformArtifact", "artifact_key", "generate_waveform"]
