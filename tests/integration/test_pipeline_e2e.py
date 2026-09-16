"""End-to-end audio mix analysis pipeline tests."""
import re
from pathlib import Path

from tests.fixtures.synthetic_audio import generate_multi_track_mix
from worker.analysis.orchestrator import AudioAnalysisOrchestrator


def test_e2e_mix_pipeline_execution(tmp_path):
    """Test entire analysis pipeline on a multi-track synthetic mix."""
    duration_sec = 60.0
    wav_data = generate_multi_track_mix(duration_sec=duration_sec, sample_rate=22050)
    mix_file = tmp_path / "test_mix.wav"
    mix_file.write_bytes(wav_data)

    stages = []
    orchestrator = AudioAnalysisOrchestrator(
        audio_path=Path(mix_file),
        duration_seconds=duration_sec,
    )

    result = orchestrator.execute_pipeline(
        progress_callback=lambda pct, stage: stages.append((pct, stage))
    )

    assert result is not None
    # Tempo: synthetic kicks at 128/130 BPM (allow half/double-time resolution)
    assert 60.0 <= result["primary_bpm"] <= 200.0
    assert 0.0 <= result["bpm_confidence"] <= 1.0
    assert isinstance(result["bpm_candidates"], list) and len(result["bpm_candidates"]) >= 1
    # Key / Camelot
    assert re.match(r"^\d{1,2}[AB]$", result["camelot_code"])
    assert result["detected_key"]
    # Loudness (EBU R128 pass over the real file)
    assert result["integrated_lufs"] < 0.0
    assert isinstance(result["true_peak_db"], float)
    # Segmentation & transitions
    assert len(result["track_segments"]) >= 1
    first = result["track_segments"][0]
    assert first["start_time_seconds"] == 0.0
    assert first["end_time_seconds"] == duration_sec
    assert isinstance(result["transitions"], list)
    assert isinstance(result["quality_findings"], list)
    # Progress reporting reached the worker
    assert len(stages) > 0
    assert all(pct >= 0.0 for pct, _ in stages)
