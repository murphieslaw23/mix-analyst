"""Unit tests for segment transition detection."""

from worker.analysis.transition_detector import (
    detect_transitions_between_segments,
    evaluate_camelot_compatibility,
)


def test_evaluate_camelot_compatibility():
    """Verify the current Camelot compatibility vocabulary."""
    assert evaluate_camelot_compatibility("8A", "8A") == "PERFECT_MATCH"
    assert evaluate_camelot_compatibility("8A", "9A") == "ENERGY_BOOST"
    assert evaluate_camelot_compatibility("8A", "8B") == "RELATIVE_KEY"
    assert evaluate_camelot_compatibility("8A", "10B") == "HARMONIC_MODULATION"


def test_detect_transitions_between_segment_boundaries():
    """Adjacent analyzed segments produce a bounded transition zone and cue points."""
    transitions = detect_transitions_between_segments(
        [
            {
                "segment_index": 1,
                "start_time_seconds": 0.0,
                "end_time_seconds": 50.0,
                "duration_seconds": 50.0,
            },
            {
                "segment_index": 2,
                "start_time_seconds": 50.0,
                "end_time_seconds": 120.0,
                "duration_seconds": 70.0,
            },
        ],
        primary_bpm=128.0,
        camelot_code="8A",
    )

    assert len(transitions) == 1
    transition = transitions[0]
    assert transition["transition_index"] == 1
    assert transition["start_time_seconds"] == 35.0
    assert transition["end_time_seconds"] == 65.0
    assert transition["cue_out_time"] == 42.0
    assert transition["cue_in_time"] == 54.0
    assert transition["camelot_compatibility"] == "PERFECT_MATCH"
    assert transition["confidence"] == 0.88
