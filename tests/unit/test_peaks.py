"""Waveform peak computation, caching and downsampling."""
import json

import pytest

from api.app.services.peaks import (
    CACHE_BUCKETS,
    compute_peaks,
    downsample_peaks,
    load_or_compute_peaks,
)
from tests.fixtures.synthetic_audio import generate_synthetic_audio


def _write_wav(path, **kwargs):
    path.write_bytes(generate_synthetic_audio(**kwargs))
    return path


def test_compute_peaks_shape_and_range(tmp_path):
    wav = _write_wav(tmp_path / "a.wav", duration_sec=5.0, bpm=120.0)
    peaks = compute_peaks(wav, 200)

    assert len(peaks) == 200
    assert all(0.0 <= v <= 1.0 for v in peaks)
    assert max(peaks) == pytest.approx(1.0)
    # Kicks on every beat: some buckets must carry real energy.
    assert sum(1 for v in peaks if v > 0.5) >= 5


def test_compute_peaks_rejects_bad_buckets(tmp_path):
    wav = _write_wav(tmp_path / "a.wav", duration_sec=2.0)
    with pytest.raises(ValueError):
        compute_peaks(wav, 0)


def test_downsample_preserves_transients():
    peaks = [0.1] * 100
    peaks[50] = 1.0
    down = downsample_peaks(peaks, 10)

    assert len(down) == 10
    assert max(down) == pytest.approx(1.0)


def test_load_or_compute_peaks_caches_and_downsamples(tmp_path):
    storage = tmp_path / "storage"
    audio_dir = storage / "assets" / "audio"
    audio_dir.mkdir(parents=True)
    _write_wav(audio_dir / "a1.wav", duration_sec=5.0, bpm=120.0)

    peaks, duration = load_or_compute_peaks(str(storage), "assets/audio/a1.wav", "a1", 500)

    assert len(peaks) == 500
    assert duration == pytest.approx(5.0, abs=0.05)
    cache_file = storage / "assets" / "derived" / "a1_peaks.json"
    assert cache_file.is_file()
    cached = json.loads(cache_file.read_text())
    assert len(cached["peaks"]) == CACHE_BUCKETS

    # Second call serves from cache (delete source buckets proof: same values).
    peaks2, _ = load_or_compute_peaks(str(storage), "assets/audio/a1.wav", "a1", 500)
    assert peaks2 == peaks


def test_load_or_compute_peaks_missing_audio(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_or_compute_peaks(str(tmp_path), "assets/audio/nope.wav", "x", 100)


def test_load_or_compute_peaks_refuses_traversal(tmp_path):
    with pytest.raises(ValueError):
        load_or_compute_peaks(str(tmp_path), "../../etc/passwd", "x", 100)
