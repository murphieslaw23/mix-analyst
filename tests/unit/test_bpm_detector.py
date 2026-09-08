"""Unit tests for the bounded-window BPM detector."""

import io

import soundfile as sf

from tests.fixtures.synthetic_audio import generate_synthetic_audio
from worker.analysis.bpm_detector import aggregate_bpm_candidates, detect_window_tempo


def _detect_primary_bpm(bpm: float) -> dict:
    wav_bytes = generate_synthetic_audio(duration_sec=15.0, bpm=bpm)
    data, sample_rate = sf.read(io.BytesIO(wav_bytes))
    window_bpm = detect_window_tempo(data, sample_rate)
    return aggregate_bpm_candidates([window_bpm])


def test_detect_window_tempo_120():
    """A steady 120 BPM window feeds the current aggregate contract."""
    result = _detect_primary_bpm(120.0)

    assert 118.0 <= result["primary_bpm"] <= 122.0
    assert result["confidence"] == 1.0
    assert result["candidates"][0]["support_count"] == 1


def test_detect_window_tempo_140():
    """A steady 140 BPM window remains close to the source tempo."""
    result = _detect_primary_bpm(140.0)

    assert 138.0 <= result["primary_bpm"] <= 142.0
