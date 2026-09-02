"""Behavioral coverage for the immutable mastering worker stage."""

import io

import soundfile as sf

from tests.fixtures.synthetic_audio import generate_synthetic_audio


def test_master_stage_writes_immutable_result_artifact(tmp_path):
    """A loudness master is written under an opaque, owner-scoped key."""
    from worker.stages.master_mix import MasterSettings, run_master_mix

    source = tmp_path / "source.wav"
    source.write_bytes(generate_synthetic_audio(duration_sec=3.0))

    result = run_master_mix(
        source,
        MasterSettings(
            target_lufs=-9.0,
            true_peak_dbtp=-1.0,
            project_id="project-a",
            storage_root=tmp_path,
        ),
    )

    assert result.integrated_lufs <= -8.5
    assert result.true_peak_dbtp <= -0.95
    assert result.artifact_key.startswith("projects/project-a/artifacts/mastered/v1/")
    artifact = tmp_path / result.artifact_key
    assert artifact.is_file()
    audio, sample_rate = sf.read(artifact, always_2d=False)
    assert sample_rate == 22050
    assert audio.size > 0
