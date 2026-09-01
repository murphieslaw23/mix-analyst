"""Unit tests for stem separator and bassline collision analyzer."""
import numpy as np
from worker.analysis.stem_separator import StemSeparatorEngine

def test_analyze_bassline_and_collision():
    """Verify bassline fundamental detection and kick/sub overlap calculation."""
    sample_rate = 22050
    t = np.linspace(0, 5, sample_rate * 5)
    
    # Bass stem: 55 Hz sine wave (A1)
    bass = 0.8 * np.sin(2.0 * np.pi * 55.0 * t)
    
    # Drums stem: 60 Hz kick transients
    drums = 0.8 * np.sin(2.0 * np.pi * 60.0 * t)
    
    result = StemSeparatorEngine.analyze_bassline_and_collision(bass, drums, sample_rate)
    
    assert result is not None
    assert 50.0 <= result["bass_fundamental_hz"] <= 60.0
    assert "kick_sub_collision_score" in result
    assert result["low_end_clarity"] in ["optimal", "moderate_clash", "high_clash"]
