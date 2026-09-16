"""Unit tests for Two-Pass Mastering Engine."""

import io

import soundfile as sf

from tests.fixtures.synthetic_audio import generate_synthetic_audio
from worker.analysis.mastering_engine import DEFAULT_PRESETS, TwoPassMasteringEngine


def test_two_pass_mastering_loudness_target():
    """Verify two-pass mastering achieves target LUFS on synthetic audio."""
    wav_bytes = generate_synthetic_audio(duration_sec=15.0, bpm=128.0)
    data, sr = sf.read(io.BytesIO(wav_bytes))

    engine = TwoPassMasteringEngine(target_lufs=-14.0, true_peak_ceiling=-1.0)
    preset = DEFAULT_PRESETS["club_broadcast"]

    processed, report = engine.process_mastering(data, sr, preset)

    assert processed is not None
    assert report["compliance_passed"] is True
    assert abs(report["output_measurements"]["integrated_lufs"] - (-14.0)) <= 1.0
    assert report["output_measurements"]["true_peak_db"] <= -0.9
