"""Unit tests for transition detector."""
import numpy as np
import pytest
from worker.analysis.transition_detector import detect_transitions, classify_energy_shift

def test_classify_energy_shift():
    """Verify energy delta classifications."""
    assert classify_energy_shift(0.05) == "stable"
    assert classify_energy_shift(0.35) == "build_up"
    assert classify_energy_shift(-0.35) == "drop"

def test_detect_transitions_boundary():
    """Verify transition points are extracted from energy curve."""
    # Synthetic energy profile with a drop/build transition at step 10
    time_series = np.linspace(0, 120, 24)
    energy_curve = [0.7] * 8 + [0.3, 0.2, 0.25] + [0.85] * 13
    
    transitions = detect_transitions(
        timestamps=time_series,
        energy_levels=energy_curve,
        detected_tracks=[
            {"start_time": 0.0, "end_time": 50.0, "bpm": 128.0, "camelot_key": "8A"},
            {"start_time": 45.0, "end_time": 120.0, "bpm": 130.0, "camelot_key": "9A"}
        ]
    )
    
    assert len(transitions) >= 1
    t = transitions[0]
    assert t["from_key"] == "8A"
    assert t["to_key"] == "9A"
    assert t["harmonic_compatibility"] in ["exact", "adjacent_major", "adjacent_minor", "compatible"]
