"""Stage test: tagging suggests a name without mutating the source object."""

import json
from pathlib import Path

from tests.fixtures.synthetic_audio import generate_synthetic_audio
from worker.stages.tag_mix import tag_mix


def _write_source(tmp_path: Path, name: str = "artist - track.wav") -> Path:
    wav_bytes = generate_synthetic_audio(duration_sec=2.0, bpm=128.0)
    path = tmp_path / name
    path.write_bytes(wav_bytes)
    return path


def test_tag_stage_is_stable_for_source_and_inputs(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    first = tag_mix(
        source,
        tmp_path / "first" / "tags.json",
        bpm=200.0,
        musical_key="8A",
        source_filename="artist - track.wav",
    )
    second = tag_mix(
        source,
        tmp_path / "second" / "tags.json",
        bpm=200.0,
        musical_key="8A",
        source_filename="artist - track.wav",
    )

    assert first.artifact_key == second.artifact_key
    assert first.artifact_key.startswith("artifacts/metadata/")
    assert first.sha256 == second.sha256
    assert first.suggested_download_name == second.suggested_download_name


def test_tagger_suggests_download_name_without_mutating_source_key(
    tmp_path: Path,
) -> None:
    source = _write_source(tmp_path)
    before = source.read_bytes()

    tagged = tag_mix(
        source,
        tmp_path / "tags.json",
        bpm=200.0,
        musical_key="8A",
        source_filename="artist - track.wav",
    )

    assert source.read_bytes() == before
    assert tagged.tags.genre == "Hardcore"
    assert tagged.suggested_download_name == "artist - track [Hardcore].wav"
    assert tagged.artifact_key != tagged.suggested_download_name
    payload = json.loads((tmp_path / "tags.json").read_bytes())
    assert payload["suggested_download_name"] == tagged.suggested_download_name
    assert payload["tags"]["bpm"] == 200.0
    assert payload["tags"]["musical_key"] == "8A"


def test_tagger_handles_missing_inputs_with_neutral_defaults(
    tmp_path: Path,
) -> None:
    source = _write_source(tmp_path, name="raw_take.wav")

    tagged = tag_mix(source, tmp_path / "tags.json")

    assert tagged.tags.genre == "Unknown"
    assert tagged.tags.artist == "Unknown Artist"
    assert tagged.tags.title == "raw take"
    assert tagged.suggested_download_name == ("Unknown Artist - raw take [Unknown].wav")
