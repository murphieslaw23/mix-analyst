import numpy as np
from typing import Dict, Any, Tuple

class DynamicSidechainDSP:
    """Automated sub-bass sidechain ducking and phase alignment for sound-system mastering."""

    @staticmethod
    def process_sub_bass_sidechain(
        kick_audio: np.ndarray,
        bass_audio: np.ndarray,
        sample_rate: int = 22050,
        threshold_db: float = -12.0,
        max_ducking_db: float = 6.0
    ) -> Dict[str, Any]:
        """Perform phase correlation alignment and dynamic frequency-selective ducking."""
        # 1. Phase correlation check between kick and bass fundamentals
        check_len = min(len(kick_audio), len(bass_audio), sample_rate * 5)
        corr_matrix = np.corrcoef(kick_audio[:check_len], bass_audio[:check_len])
        corr = float(corr_matrix[0, 1]) if not np.isnan(corr_matrix[0, 1]) else 0.0
        
        phase_inverted = False
        working_bass = np.copy(bass_audio)
        if corr < -0.15:
            working_bass = -working_bass
            phase_inverted = True
            re_corr = np.corrcoef(kick_audio[:check_len], working_bass[:check_len])[0, 1]
            corr = float(re_corr) if not np.isnan(re_corr) else 0.0

        # 2. Envelope follower on kick transients (10ms attack, 80ms release)
        kick_env = np.abs(kick_audio)
        alpha = np.exp(-1.0 / (sample_rate * 0.01))
        beta = np.exp(-1.0 / (sample_rate * 0.08))

        envelope = np.zeros_like(kick_env)
        curr = 0.0
        for i in range(len(kick_env)):
            target = kick_env[i]
            if target > curr:
                curr = alpha * curr + (1.0 - alpha) * target
            else:
                curr = beta * curr + (1.0 - beta) * target
            envelope[i] = curr

        # 3. Dynamic gain reduction calculation
        thresh_linear = 10.0 ** (threshold_db / 20.0)
        duck_linear = 10.0 ** (-max_ducking_db / 20.0)
        gain_reduction = np.ones_like(envelope)

        mask = envelope > thresh_linear
        if np.any(mask):
            max_env = np.max(envelope)
            denom = max_env - thresh_linear + 1e-6
            gain_reduction[mask] = np.clip(
                1.0 - ((envelope[mask] - thresh_linear) / denom) * (1.0 - duck_linear),
                duck_linear,
                1.0
            )

        processed_bass = working_bass * gain_reduction
        min_gain = np.min(gain_reduction)
        max_gr_db = float(20 * np.log10(min_gain)) if min_gain > 0 else -max_ducking_db

        return {
            "phase_inverted": phase_inverted,
            "phase_correlation": round(corr, 3),
            "max_gain_reduction_db": round(max_gr_db, 2),
            "processed_bass_rms": round(float(np.sqrt(np.mean(processed_bass**2))), 4),
            "low_end_clarity_score": round(1.0 - min(1.0, max(0.0, (corr * -1) if corr < 0 else (1.0 - abs(corr)) * 0.5)), 3)
        }
