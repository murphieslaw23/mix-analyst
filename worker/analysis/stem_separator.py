"""Stem separation and bassline collision analyzer engine."""
import numpy as np
from typing import Dict, Any, Tuple

class StemSeparatorEngine:
    """Dispatches stem extraction and analyzes low-end kick/bass interaction."""

    @staticmethod
    def analyze_bassline_and_collision(bass_audio: np.ndarray, drums_audio: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Analyze sub-bass fundamentals, kick/sub spectral overlap, and 303 resonance."""
        # Calculate FFT spectra for bass and drums in sub range (20Hz - 150Hz)
        fft_len = 2048
        bass_fft = np.abs(np.fft.rfft(bass_audio[:sample_rate * 10], n=fft_len))
        drums_fft = np.abs(np.fft.rfft(drums_audio[:sample_rate * 10], n=fft_len))
        freqs = np.fft.rfftfreq(fft_len, 1.0 / sample_rate)

        # Sub range mask (30Hz - 120Hz)
        sub_mask = (freqs >= 30.0) & (freqs <= 120.0)
        sub_bass_energy = np.sum(bass_fft[sub_mask])
        sub_kick_energy = np.sum(drums_fft[sub_mask])

        # Fundamental frequency of the bass stem
        sub_indices = np.where(sub_mask)[0]
        if len(sub_indices) > 0:
            peak_idx = sub_indices[np.argmax(bass_fft[sub_indices])]
            fundamental_hz = float(freqs[peak_idx])
        else:
            fundamental_hz = 55.0

        # Collision score: normalized dot product of sub spectra
        overlap = np.sum(bass_fft[sub_mask] * drums_fft[sub_mask])
        denom = (np.linalg.norm(bass_fft[sub_mask]) * np.linalg.norm(drums_fft[sub_mask])) + 1e-6
        collision_score = float(np.clip(overlap / denom, 0.0, 1.0))

        return {
            "bass_fundamental_hz": round(fundamental_hz, 1),
            "kick_sub_collision_score": round(collision_score, 3),
            "low_end_clarity": "optimal" if collision_score < 0.4 else "moderate_clash" if collision_score < 0.7 else "high_clash",
            "resonance_peaks": [round(fundamental_hz, 1), round(fundamental_hz * 2, 1)]
        }
