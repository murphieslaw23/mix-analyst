"""Metadata reports provide presentation names without changing source identity."""

import hashlib

from tests.fixtures.synthetic_audio import generate_synthetic_audio


def test_tagger_suggests_download_name_without_mutating_source_key(tmp_path):
    from worker.stages.tag_mix import Artifact, tag_mix

    source = tmp_path / "Teknoid - live @ warehouse (2025-02-14).wav"
    source.write_bytes(generate_synthetic_audio(duration_sec=2.0, bpm=150.0))
    source_artifact = Artifact(
        role="source",
        key="projects/project-a/artifacts/source/v1/" + "a" * 64,
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        algorithm_version="v1",
        media_type="audio/wav",
        byte_length=source.stat().st_size,
    )

    tagged_mix = tag_mix(source, source_artifact, source.name, algorithm_version="1")

    assert tagged_mix.source_artifact.key != tagged_mix.suggested_download_name
    assert tagged_mix.metadata_artifact.key.startswith("artifacts/metadata/1/")
    assert tagged_mix.metadata_artifact.sha256 == hashlib.sha256(tagged_mix.payload).hexdigest()
    assert tagged_mix.suggested_download_name.endswith(".wav")
