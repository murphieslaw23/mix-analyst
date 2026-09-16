"""Waveform peak computation with on-disk caching.

Peaks are computed once per mix at fixed resolution (2000 buckets) by
streaming the audio file in blocks (bounded memory even for multi-hour
sets) and cached as JSON next to the derived assets. Requests for fewer
buckets downsample peak-preservingly with max() grouping.
"""

import json
import os
from pathlib import Path

import numpy as np
import soundfile as sf

CACHE_BUCKETS = 2000


def compute_peaks(audio_path: Path, buckets: int) -> list[float]:
    """Stream peak amplitude per bucket (mono mixdown, normalized 0..1)."""
    if buckets <= 0:
        raise ValueError("buckets must be positive")
    with sf.SoundFile(str(audio_path), "r") as handle:
        total = len(handle)
        if total <= 0:
            return [0.0] * buckets
        peaks = np.zeros(buckets, dtype=np.float64)
        position = 0
        for block in handle.blocks(blocksize=65536, dtype="float32", always_2d=True):
            mono = np.abs(block.mean(axis=1))
            frames = np.arange(position, position + len(mono))
            idx = np.minimum((frames * buckets) // total, buckets - 1)
            np.maximum.at(peaks, idx, mono)
            position += len(mono)
    peak_max = float(peaks.max()) if peaks.size else 0.0
    if peak_max > 0:
        peaks /= peak_max
    return [round(float(v), 4) for v in peaks]


def downsample_peaks(peaks: list[float], buckets: int) -> list[float]:
    """Reduce peak resolution with max() grouping (never hides transients)."""
    if buckets <= 0:
        raise ValueError("buckets must be positive")
    if len(peaks) <= buckets:
        return list(peaks)
    size = len(peaks) / buckets
    return [max(peaks[int(i * size) : int((i + 1) * size)]) for i in range(buckets)]


def load_or_compute_peaks(
    storage_root: str, rel_path: str, asset_id: str, buckets: int
) -> tuple[list[float], float]:
    """Return (peaks, duration_seconds), using the JSON cache when fresh."""
    root = Path(storage_root).resolve()
    audio_abs = (root / rel_path).resolve()
    if not str(audio_abs).startswith(str(root)):
        raise ValueError(f"Refusing to read outside storage root: {rel_path}")
    cache_path = root / "assets" / "derived" / f"{asset_id}_peaks.json"

    if not audio_abs.is_file():
        raise FileNotFoundError(f"Audio file missing on storage: {rel_path}")

    audio_mtime = audio_abs.stat().st_mtime
    cached: dict = {}
    if cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text())
        except (OSError, ValueError):
            cached = {}

    if (
        cached.get("mtime") == audio_mtime
        and len(cached.get("peaks", [])) == CACHE_BUCKETS
    ):
        full = [float(v) for v in cached["peaks"]]
        duration = float(cached.get("duration_seconds", 0.0))
    else:
        with sf.SoundFile(str(audio_abs), "r") as handle:
            duration = len(handle) / float(handle.samplerate)
        full = compute_peaks(audio_abs, CACHE_BUCKETS)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = cache_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(
                {"mtime": audio_mtime, "duration_seconds": duration, "peaks": full}
            )
        )
        os.replace(tmp_path, cache_path)

    return downsample_peaks(full, buckets), duration
