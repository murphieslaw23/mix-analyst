"""End-to-end coverage for the current bounded audio analysis orchestrator."""

from tests.fixtures.synthetic_audio import generate_multi_track_mix
from worker.analysis.orchestrator import AudioAnalysisOrchestrator


def test_e2e_mix_pipeline_execution(tmp_path, monkeypatch):
    """Run real window/loudness analysis while keeping network fingerprint lookup deterministic."""
    wav_data = generate_multi_track_mix(duration_sec=30.0, sample_rate=22050)
    mix_file = tmp_path / "test_mix.wav"
    mix_file.write_bytes(wav_data)

    monkeypatch.setattr(
        "worker.analysis.orchestrator.generate_audio_fingerprint",
        lambda _path, _offset, duration_seconds=60.0: {
            "fingerprint": "fixture",
            "duration": duration_seconds,
        },
    )
    monkeypatch.setattr(
        "worker.analysis.orchestrator.query_acoustid_metadata",
        lambda *_args, **_kwargs: None,
    )

    progress = []
    orchestrator = AudioAnalysisOrchestrator(audio_path=mix_file, duration_seconds=30.0)
    result = orchestrator.execute_pipeline(
        lambda percent, stage: progress.append((percent, stage))
    )

    assert result is not None
    assert result["primary_bpm"] > 0
    assert result["bpm_confidence"] >= 0
    assert result["detected_key"]
    assert result["camelot_code"]
    assert isinstance(result["integrated_lufs"], float)
    assert isinstance(result["track_segments"], list)
    assert isinstance(result["transitions"], list)
    assert progress[0][0] == 10.0
    assert progress[-1][0] == 94.0
