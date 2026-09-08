import math
from collections import Counter
from typing import Any

import librosa
import numpy as np

# Krumhansl-Kessler Musical Pitch Profiles (C, C#, D, D#, E, F, F#, G, G#, A, A#, B)
MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

CAMELOT_MAP = {
    "C major": "8B",
    "A minor": "8A",
    "G major": "9B",
    "E minor": "9A",
    "D major": "10B",
    "B minor": "10A",
    "A major": "11B",
    "F# minor": "11A",
    "E major": "12B",
    "C# minor": "12A",
    "B major": "1B",
    "G# minor": "1A",
    "F# major": "2B",
    "D# minor": "2A",
    "C# major": "3B",
    "A# minor": "3A",
    "G# major": "4B",
    "F minor": "4A",
    "D# major": "5B",
    "C minor": "5A",
    "A# major": "6B",
    "G minor": "6A",
    "F major": "7B",
    "D minor": "7A",
}


def pearson_correlation(v1: list[float], v2: list[float]) -> float:
    n = len(v1)
    mean1 = sum(v1) / n
    mean2 = sum(v2) / n

    num = sum((a - mean1) * (b - mean2) for a, b in zip(v1, v2))
    den1 = math.sqrt(sum((a - mean1) ** 2 for a in v1))
    den2 = math.sqrt(sum((b - mean2) ** 2 for b in v2))

    if den1 == 0 or den2 == 0:
        return 0.0
    return num / (den1 * den2)


def detect_window_key(y: np.ndarray, sr: int) -> tuple[str, str, float]:
    """Detect key, Camelot code, and correlation confidence for an audio window."""
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    chroma_vector = np.mean(chroma, axis=1).tolist()

    best_corr = -1.0
    best_key = "C major"

    for shift in range(12):
        rotated_chroma = [chroma_vector[(shift + i) % 12] for i in range(12)]

        # Check Major
        corr_maj = pearson_correlation(rotated_chroma, MAJOR_PROFILE)
        if corr_maj > best_corr:
            best_corr = corr_maj
            best_key = f"{PITCH_NAMES[shift]} major"

        # Check Minor
        corr_min = pearson_correlation(rotated_chroma, MINOR_PROFILE)
        if corr_min > best_corr:
            best_corr = corr_min
            best_key = f"{PITCH_NAMES[shift]} minor"

    camelot = CAMELOT_MAP.get(best_key, "8B")
    confidence = round(max(0.0, min(1.0, (best_corr + 1) / 2)), 2)

    return best_key, camelot, confidence


def aggregate_key_predictions(
    window_keys: list[tuple[str, str, float]],
) -> dict[str, Any]:
    """Aggregate window key detections into a consolidated key & Camelot prediction."""
    if not window_keys:
        return {"detected_key": "C major", "camelot_code": "8B", "key_confidence": 0.0}

    keys = [k[0] for k in window_keys]
    counter = Counter(keys)
    primary_key, highest_votes = counter.most_common(1)[0]
    camelot = CAMELOT_MAP.get(primary_key, "8B")
    confidence = round(highest_votes / len(window_keys), 2)

    return {
        "detected_key": primary_key,
        "camelot_code": camelot,
        "key_confidence": confidence,
    }
