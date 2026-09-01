"""Unit tests for BPM detection."""
import io
import pytest
import numpy as np
from tests.fixtures.synthetic_audio import generate_synthetic_audio
from worker.analysis.bpm_detector import detect_bpm

def test_detect_bpm_120():
    """Verify BPM detector resolves steady 120 BPM."""
    wav_bytes = generate_synthetic_audio(duration_sec=15.0, bpm=120.0)
    # Convert bytes back to float array
    import soundfile as sf
    data, sr = sf.read(io.BytesIO(wav_bytes))
    
    result = detect_bpm(data, sr)
    assert result is not None
    assert "bpm" in result
    assert 118.0 <= result["bpm"] <= 122.0
    assert result["confidence"] > 0.6

def test_detect_bpm_140():
    """Verify BPM detector resolves steady 140 BPM."""
    wav_bytes = generate_synthetic_audio(duration_sec=15.0, bpm=140.0)
    import soundfile as sf
    data, sr = sf.read(io.BytesIO(wav_bytes))
    
    result = detect_bpm(data, sr)
    assert result is not None
    assert 138.0 <= result["bpm"] <= 142.0
