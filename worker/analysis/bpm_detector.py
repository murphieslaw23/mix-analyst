import numpy as np
import librosa
from typing import List, Dict, Any
from collections import Counter


def detect_window_tempo(y: np.ndarray, sr: int) -> float:
    """Detect primary tempo for a single audio window."""
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, aggregate=np.median)
    if isinstance(tempo, np.ndarray):
        tempo_val = float(tempo[0]) if len(tempo) > 0 else 120.0
    else:
        tempo_val = float(tempo)
    return round(tempo_val, 1)


def aggregate_bpm_candidates(window_tempos: List[float]) -> Dict[str, Any]:
    """
    Aggregate detected window tempos into primary BPM and candidate hypotheses.
    Handles half-time and double-time resolutions (e.g. 85 / 170 BPM).
    """
    if not window_tempos:
        return {"primary_bpm": 120.0, "confidence": 0.0, "candidates": []}

    # Bin tempos to nearest 0.5 BPM
    binned = [round(t * 2) / 2 for t in window_tempos if t > 0]
    if not binned:
        return {"primary_bpm": 120.0, "confidence": 0.0, "candidates": []}

    counter = Counter(binned)
    total_votes = len(binned)

    sorted_candidates = counter.most_common()
    primary_bpm, highest_votes = sorted_candidates[0]
    confidence = round(highest_votes / total_votes, 2)

    candidates_list = []
    for bpm, count in sorted_candidates:
        candidates_list.append({
            "bpm": float(bpm),
            "confidence": round(count / total_votes, 2),
            "support_count": count,
        })

    return {
        "primary_bpm": float(primary_bpm),
        "confidence": confidence,
        "candidates": candidates_list,
    }
