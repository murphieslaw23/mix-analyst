"""Stage test: mastering writes one immutable, deterministic artifact."""

from pathlib import Path

import soundfile as sf

from tests.fixtures.synthetic_audio import generate_synthetic_audio
from worker.dsp.mastering import MasterSettings
from worker.stages.master_mix import master_mix


def _write_source(tmp_path: Path, name: str = "source.wav") -> Path:
    wav_bytes = generate_synthetic_audio(duration_sec=6.0, bpm=128.0)
    path = tmp_path / name
    path.write_bytes(wav_bytes)
    return path


def test_master_stage_writes_immutable_result_artifact(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    settings = MasterSettings(target_lufs=-14.0, true_peak_dbtp=-1.0)

    first = master_mix(source, tmp_path / "first" / "master.wav", settings)
    second = master_mix(source, tmp_path / "second" / "master.wav", settings)

    assert first.artifact_key == second.artifact_key
    assert first.artifact_key.startswith("artifacts/master/")
    assert first.algorithm_version == "twopass-mastering/1.0.0"
    assert abs(first.integrated_lufs - second.integrated_lufs) <= 0.1
    assert abs(first.true_peak_dbtp - second.true_peak_dbtp) <= 0.1


def test_master_stage_output_meets_target_and_ceiling(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    dest = tmp_path / "master.wav"
    settings = MasterSettings(target_lufs=-14.0, true_peak_dbtp=-1.0)

    result = master_mix(source, dest, settings)

    assert dest.is_file()
    audio, sample_rate = sf.read(str(dest))
    assert audio.size > 0 and sample_rate > 0
    assert abs(result.integrated_lufs - settings.target_lufs) <= 1.0
    assert result.true_peak_dbtp <= settings.true_peak_dbtp + 0.2


def test_master_stage_rejects_missing_source(tmp_path: Path) -> None:
    try:
        master_mix(
            tmp_path / "absent.wav",
            tmp_path / "master.wav",
            MasterSettings(target_lufs=-14.0, true_peak_dbtp=-1.0),
        )
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError for a missing source")
