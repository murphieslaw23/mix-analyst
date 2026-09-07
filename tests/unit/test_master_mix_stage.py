"""Behavioral coverage for the immutable mastering worker stage."""

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


def test_custom_profile_controls_reach_the_mastering_dsp_stage(tmp_path, monkeypatch):
    """Selected LRA, EQ, and compressor values must affect the worker DSP path."""
    import worker.dsp.mastering as mastering

    source = tmp_path / "profile-source.wav"
    source.write_bytes(generate_synthetic_audio(duration_sec=3.0))
    captured = {}
    original_eq = mastering._apply_profile_eq
    original_compressor = mastering._apply_profile_compression

    def capture_eq(audio, sample_rate, settings):
        captured["eq"] = dict(settings)
        return original_eq(audio, sample_rate, settings)

    def capture_compressor(audio, sample_rate, target_lra, settings):
        captured["target_lra"] = target_lra
        captured["compressor"] = dict(settings)
        return original_compressor(audio, sample_rate, target_lra, settings)

    monkeypatch.setattr(mastering, "_apply_profile_eq", capture_eq)
    monkeypatch.setattr(mastering, "_apply_profile_compression", capture_compressor)
    settings = mastering.MasterSettings(
        target_lufs=-12.0,
        true_peak_dbtp=-1.0,
        target_lra=5.5,
        eq_settings={"sub_boost_db": 3.0, "mud_cut_db": -2.0, "high_air_db": 1.5},
        compressor_settings={"threshold_db": -20.0, "ratio": 3.5, "attack_ms": 12.0, "release_ms": 160.0},
        project_id="project-a",
        storage_root=tmp_path,
    )

    mastering.master_audio_file(source, settings)

    assert captured == {
        "eq": {"sub_boost_db": 3.0, "mud_cut_db": -2.0, "high_air_db": 1.5},
        "target_lra": 5.5,
        "compressor": {"threshold_db": -20.0, "ratio": 3.5, "attack_ms": 12.0, "release_ms": 160.0},
    }


def test_long_mastering_uses_streaming_path_instead_of_soundfile_read(tmp_path, monkeypatch):
    """A recording beyond the array cap must never be decoded as one NumPy array."""
    import worker.dsp.mastering as mastering

    source = tmp_path / "long-source.wav"
    source.write_bytes(generate_synthetic_audio(duration_sec=9.0))

    def fail_whole_file_decode(*_args, **_kwargs):
        raise AssertionError("long-form mastering attempted whole-file soundfile.read")

    monkeypatch.setattr(sf, "read", fail_whole_file_decode)
    result = mastering.master_audio_file(
        source,
        mastering.MasterSettings(project_id="project-a", storage_root=tmp_path),
    )

    assert result.artifact_key.startswith("projects/project-a/artifacts/mastered/v1/")
    assert (tmp_path / result.artifact_key).is_file()
    assert result.true_peak_dbtp <= -0.5
