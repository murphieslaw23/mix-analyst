"""Deterministic waveform extraction primitives.

The DSP layer deliberately returns data rather than touching storage.  That
keeps the calculation repeatable and leaves owner-scoped object persistence to
the worker stage.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def extract_peaks(source: Path, points: int) -> tuple[list[float], int, float]:
    """Return normalized block-max mono peaks for a trusted audio source."""
    import soundfile as sf

    if points < 1:
        raise ValueError("points must be positive")
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError("waveform source artifact does not exist")

    audio, sample_rate = sf.read(path, always_2d=True, dtype="float32")
    if audio.size == 0:
        raise ValueError("audio is empty")
    mono = np.mean(audio, axis=1, dtype=np.float32)
    edges = np.linspace(0, mono.size, points + 1, dtype=np.int64)
    peaks = np.empty(points, dtype=np.float32)
    for index in range(points):
        block = mono[edges[index] : edges[index + 1]]
        peaks[index] = float(np.max(np.abs(block))) if block.size else 0.0
    maximum = float(np.max(peaks)) if peaks.size else 0.0
    if maximum > 1.0:
        peaks /= maximum
    return peaks.round(6).tolist(), int(sample_rate), round(float(mono.size / sample_rate), 6)


__all__ = ["extract_peaks"]
