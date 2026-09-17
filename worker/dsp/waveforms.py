"""Deterministic waveform peak extraction with bounded memory.

The DSP layer returns data rather than touching storage: peaks stream through
fixed-size soundfile blocks, so memory stays flat however long the source is.
Persistence belongs to ``worker.stages.generate_waveform``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

WAVEFORM_ALGORITHM_VERSION = "waveform-peaks/1.0.0"
WAVEFORM_ARTIFACT_ROLE = "waveform"
_STREAM_BLOCKSIZE = 65536


def compute_waveform(source: Path, points: int) -> list[float]:
    """Return normalized block-max mono peaks in the 0..1 range.

    Peaks are deterministic for the same input bytes and point count: each
    frame maps to ``min(frame_index * points // total_frames, points - 1)``
    and each window keeps its maximum absolute mono amplitude. Values above
    full scale are renormalized so the result always fits 0..1.
    """
    if points < 1:
        raise ValueError("points must be positive")
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError("waveform source artifact does not exist")

    with sf.SoundFile(str(path), "r") as handle:
        total_frames = len(handle)
        if total_frames <= 0:
            raise ValueError("audio is empty")
        peaks = np.zeros(points, dtype=np.float64)
        start = 0
        while True:
            block = handle.read(_STREAM_BLOCKSIZE, dtype="float32", always_2d=True)
            frame_count = block.shape[0]
            if frame_count == 0:
                break
            mono = np.abs(block.mean(axis=1, dtype=np.float64))
            indexes = (np.arange(start, start + frame_count) * points) // total_frames
            np.maximum.at(peaks, np.clip(indexes, 0, points - 1), mono)
            start += frame_count

    maximum = float(np.max(peaks)) if peaks.size else 0.0
    if maximum > 1.0:
        peaks /= maximum
    np.clip(peaks, 0.0, 1.0, out=peaks)
    return [round(float(value), 6) for value in peaks.tolist()]


__all__ = [
    "WAVEFORM_ALGORITHM_VERSION",
    "WAVEFORM_ARTIFACT_ROLE",
    "compute_waveform",
]
