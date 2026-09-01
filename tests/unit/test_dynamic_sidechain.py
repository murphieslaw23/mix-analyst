import numpy as np
from worker.analysis.dynamic_sidechain import DynamicSidechainDSP

def test_dynamic_sidechain_ducking():
    """Verify envelope follower and dynamic sub-bass gain reduction."""
    sr = 22050
    t = np.linspace(0, 5, sr * 5)
    kick = np.sin(2.0 * np.pi * 55.0 * t) * (t % 0.5 < 0.1)
    bass = np.sin(2.0 * np.pi * 55.0 * t)

    res = DynamicSidechainDSP.process_sub_bass_sidechain(kick, bass, sr, threshold_db=-15.0, max_ducking_db=6.0)

    assert "max_gain_reduction_db" in res
    assert res["max_gain_reduction_db"] <= -3.0
    assert res["processed_bass_rms"] > 0

def test_phase_alignment_inversion():
    """Verify automatic 180-degree phase flip when kick and sub are out of phase."""
    sr = 22050
    t = np.linspace(0, 5, sr * 5)
    kick = np.sin(2.0 * np.pi * 55.0 * t)
    bass = -np.sin(2.0 * np.pi * 55.0 * t) # Inverse polarity

    res = DynamicSidechainDSP.process_sub_bass_sidechain(kick, bass, sr)

    assert res["phase_inverted"] is True
    assert res["phase_correlation"] > 0
