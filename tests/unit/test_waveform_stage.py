"""Stage test: waveform peaks are deterministic for the same input."""

import json
from pathlib import Path

import pytest

from tests.fixtures.synthetic_audio import generate_synthetic_audio
from worker.dsp.waveforms import compute_waveform
from worker.stages.generate_waveform import generate_waveform


def _write_source(tmp_path: Path, name: str = "source.wav") -> Path:
    wav_bytes = generate_synthetic_audio(duration_sec=4.0, bpm=128.0)
    path = tmp_path / name
    path.write_bytes(wav_bytes)
    return path


def test_waveform_key_is_stable_for_source_and_algorithm(
    tmp_path: Path,
) -> None:
    source = _write_source(tmp_path)
    first = generate_waveform(source, tmp_path / "first" / "waveform.json", points=512)
    second = generate_waveform(
        source, tmp_path / "second" / "waveform.json", points=512
    )

    assert first.sha256 == second.sha256
    assert first.artifact_key == second.artifact_key
    assert first.artifact_key.startswith("artifacts/waveform/")
    assert first.peaks == second.peaks


def test_waveform_peaks_are_normalized_and_cover_duration(
    tmp_path: Path,
) -> None:
    source = _write_source(tmp_path)
    dest = tmp_path / "waveform.json"

    result = generate_waveform(source, dest, points=256)

    assert len(result.peaks) == 256
    assert all(0.0 <= peak <= 1.0 for peak in result.peaks)
    assert max(result.peaks) > 0.0
    assert result.duration_seconds == pytest.approx(4.0, abs=0.01)
    payload = json.loads(dest.read_bytes())
    assert payload["points"] == 256
    assert list(payload["peaks"]) == list(result.peaks)


def test_compute_waveform_rejects_bad_inputs(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    with pytest.raises(ValueError):
        compute_waveform(source, 0)
    with pytest.raises(FileNotFoundError):
        compute_waveform(tmp_path / "absent.wav", 128)
