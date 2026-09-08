"""Pure metadata analysis and download-name suggestion primitives."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

GENRE_PROFILES = {
    "Freetekno": {"bpm": (140, 180), "spectral": "mid-balanced"},
    "Jungle": {"bpm": (155, 175), "spectral": "bass-heavy"},
    "Hardcore": {"bpm": (165, 220), "spectral": "high-energy"},
    "Tekno": {"bpm": (140, 160), "spectral": "sub-focused"},
    "Breakcore": {"bpm": (160, 300), "spectral": "broad-spectrum"},
    "Acidcore": {"bpm": (150, 185), "spectral": "mid-resonant"},
}


@dataclass(frozen=True)
class TagReport:
    bpm: float
    key: str
    spectral_centroid_hz: float
    spectral_profile: str
    genre: str
    genre_scores: dict[str, float]
    duration_seconds: float
    sample_rate: int

    def as_dict(self) -> dict:
        return asdict(self)


def _estimate_key(chroma: np.ndarray) -> str:
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    profile = np.asarray(chroma).mean(axis=1)
    if profile.size != 12 or not np.isfinite(profile).any():
        return "Unknown"
    return f"{names[int(np.nanargmax(profile))]} (mode undetermined)"


def _bpm_score(bpm: float, low: float, high: float) -> float:
    if low <= bpm <= high:
        return 1.0
    distance = low - bpm if bpm < low else bpm - high
    return max(0.0, 1.0 - distance / max(20.0, high - low))


def _spectral_score(actual: str, expected: str) -> float:
    if actual == expected:
        return 1.0
    aliases = {
        "broad-spectrum": {"high-energy", "mid-balanced"},
        "mid-balanced": {"mid-resonant"},
        "mid-resonant": {"mid-balanced"},
    }
    return (
        0.55
        if actual in aliases.get(expected, set())
        or expected in aliases.get(actual, set())
        else 0.2
    )


def score_genres(
    bpm: float, centroid_hz: float, spectral_profile: str | None = None
) -> dict[str, float]:
    profile = spectral_profile or (
        "high-energy" if centroid_hz > 4200 else "mid-balanced"
    )
    return {
        name: round(
            0.7 * _bpm_score(bpm, *values["bpm"])
            + 0.3 * _spectral_score(profile, values["spectral"]),
            4,
        )
        for name, values in GENRE_PROFILES.items()
    }


def _spectral_profile(
    librosa, samples: np.ndarray, sample_rate: int, centroid_hz: float
) -> str:
    spectrum = np.abs(librosa.stft(samples, n_fft=2048, hop_length=1024))
    frequencies = librosa.fft_frequencies(sr=sample_rate, n_fft=2048)
    power = np.square(spectrum).mean(axis=1) + 1e-12
    total = power.sum()

    def band(low: int, high: int) -> float:
        return float(power[(frequencies >= low) & (frequencies < high)].sum() / total)

    sub, bass, mid, high = (
        band(20, 100),
        band(100, 250),
        band(250, 2000),
        band(6000, 16000),
    )
    if high + mid > 0.55 or centroid_hz > 4200:
        return "high-energy" if high > 0.18 else "broad-spectrum"
    if sub > 0.22:
        return "sub-focused"
    if bass > 0.34:
        return "bass-heavy"
    if mid > 0.42:
        return "mid-resonant"
    return "mid-balanced"


def analyze_audio(source: Path, max_seconds: float = 120.0) -> TagReport:
    """Port the local BPM/key/genre analysis without mutating the source file."""
    if max_seconds <= 0:
        raise ValueError("max_seconds must be positive")
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - deployment dependency error
        raise RuntimeError("librosa is required for metadata analysis") from exc

    samples, sample_rate = librosa.load(
        str(source), sr=None, mono=True, duration=max_seconds
    )
    if samples.size == 0:
        raise ValueError("audio is empty")
    samples = np.nan_to_num(samples.astype(np.float32), copy=False)
    onset = librosa.onset.onset_strength(y=samples, sr=sample_rate)
    tempo, _ = librosa.beat.beat_track(onset_envelope=onset, sr=sample_rate)
    bpm = float(np.asarray(tempo).reshape(-1)[0]) if np.asarray(tempo).size else 0.0
    key = _estimate_key(librosa.feature.chroma_cqt(y=samples, sr=sample_rate))
    centroid = librosa.feature.spectral_centroid(y=samples, sr=sample_rate)
    centroid_hz = float(np.nanmedian(centroid)) if centroid.size else 0.0
    profile = _spectral_profile(librosa, samples, int(sample_rate), centroid_hz)
    scores = score_genres(bpm, centroid_hz, profile)
    return TagReport(
        bpm=round(bpm, 2),
        key=key,
        spectral_centroid_hz=round(centroid_hz, 2),
        spectral_profile=profile,
        genre=max(scores, key=scores.get),
        genre_scores=scores,
        duration_seconds=round(float(samples.size / sample_rate), 6),
        sample_rate=int(sample_rate),
    )


def suggest_download_name(filename: str, genre: str, extension: str = ".wav") -> str:
    """Return a normalized presentation name; this never changes an object key."""
    original = Path(filename).name
    stem = Path(original).stem
    live = re.match(
        r"^(?P<artist>.+?)\s*-?\s*live\s*@\s*(?P<venue>[^\[\](){}]+?)",
        stem,
        re.IGNORECASE,
    )
    parts = re.split(r"\s+[-–—]\s+", stem, maxsplit=1)
    artist, title = (
        (parts[0], parts[1])
        if len(parts) == 2
        else ("Unknown Artist", re.sub(r"_+", " ", stem).strip() or "Untitled")
    )
    if live:
        artist, title = live.group("artist"), "Live Set"
    safe = lambda value: re.sub(r'[\\/:*?"<>|]+', "", str(value)).strip()
    suffix = extension if extension.startswith(".") else f".{extension}"
    return f"{safe(artist) or 'Unknown Artist'} - {safe(title) or 'Untitled'} [{safe(genre) or 'Neutral'}]{suffix}"


__all__ = [
    "GENRE_PROFILES",
    "TagReport",
    "analyze_audio",
    "score_genres",
    "suggest_download_name",
]
