"""Deterministic coverage for the immutable waveform stage."""

import hashlib
import json

from tests.fixtures.synthetic_audio import generate_synthetic_audio


def test_waveform_key_is_stable_for_source_and_algorithm(tmp_path):
    from worker.stages.generate_waveform import generate_waveform

    source = tmp_path / "synthetic.wav"
    source.write_bytes(generate_synthetic_audio(duration_sec=2.0))

    first = generate_waveform(source, points=2048, algorithm_version="1")
    second = generate_waveform(source, points=2048, algorithm_version="1")

    assert first.sha256 == second.sha256
    assert first.key == second.key
    assert first.key == f"artifacts/waveform/1/{hashlib.sha256(source.read_bytes()).hexdigest()}"
    assert first.byte_length == len(first.payload)
    assert json.loads(first.payload)["points"] == 2048
