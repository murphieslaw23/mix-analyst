"""End-to-End audio mix analysis pipeline tests."""
import io
import pytest
import soundfile as sf
from tests.fixtures.synthetic_audio import generate_multi_track_mix
from worker.analysis.orchestrator import MixOrchestrator

def test_e2e_mix_pipeline_execution(tmp_path):
    """Test entire analysis pipeline on a multi-track synthetic mix."""
    wav_data = generate_multi_track_mix(duration_sec=30.0, sample_rate=22050)
    mix_file = tmp_path / "test_mix.wav"
    mix_file.write_bytes(wav_data)
    
    orchestrator = MixOrchestrator(
        file_path=str(mix_file),
        window_size_sec=10.0,
        hop_size_sec=5.0
    )
    
    result = orchestrator.run_pipeline()
    
    assert result is not None
    assert "duration" in result
    assert result["duration"] >= 29.0
    assert "global_bpm" in result
    assert "global_loudness" in result
    assert "transitions" in result
    assert isinstance(result["transitions"], list)
