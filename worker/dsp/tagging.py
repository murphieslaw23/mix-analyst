"""Pure metadata normalization and download-name suggestion primitives.

This module never touches storage: it normalizes already-measured BPM/key
inputs (as produced by ``worker.analysis.bpm_detector`` and
``worker.analysis.key_detector``) into a stable tag dict and builds a
human-facing suggested download name. Audio analysis itself stays out of this
layer so it depends on the standard library only.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

TAG_ALGORITHM_VERSION = "tag-mix/1.0.0"
TAG_ARTIFACT_ROLE = "metadata"
UNKNOWN_GENRE = "Unknown"

GENRE_PROFILES: dict[str, tuple[float, float]] = {
    "Freetekno": (140.0, 180.0),
    "Jungle": (155.0, 175.0),
    "Hardcore": (165.0, 220.0),
    "Tekno": (140.0, 160.0),
    "Breakcore": (160.0, 300.0),
    "Acidcore": (150.0, 185.0),
}

_LIVE_AT_PATTERN = re.compile(
    r"^(?P<artist>.+?)\s*-?\s*live\s*@\s*(?P<venue>[^\[\](){}]+?)\s*$",
    re.IGNORECASE,
)
_SPLIT_PATTERN = re.compile(r"\s+[-–—]\s+")
_UNSAFE_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|]+')


@dataclass(frozen=True)
class NormalizedTags:
    """Normalized tag values for one mix; storage keys are never derived here."""

    bpm: float | None
    musical_key: str | None
    genre: str
    genre_scores: dict[str, float] = field(default_factory=dict)
    artist: str = "Unknown Artist"
    title: str = "Untitled"

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable view of the normalized tags."""
        return asdict(self)


def _bpm_score(bpm: float, low: float, high: float) -> float:
    if low <= bpm <= high:
        return 1.0
    distance = low - bpm if bpm < low else bpm - high
    return max(0.0, 1.0 - distance / max(20.0, high - low))


def score_genres(bpm: float | None) -> dict[str, float]:
    """Score genre hypotheses from BPM alone (spectral weighting needs audio)."""
    if bpm is None:
        return {name: 0.0 for name in GENRE_PROFILES}
    return {
        name: round(_bpm_score(bpm, low, high), 4)
        for name, (low, high) in GENRE_PROFILES.items()
    }


def normalize_bpm(bpm: float | None) -> float | None:
    """Round a measured BPM to two decimals; non-positive values become None."""
    if bpm is None:
        return None
    value = round(float(bpm), 2)
    return value if value > 0 else None


def normalize_key(musical_key: str | None) -> str | None:
    """Strip whitespace from a detected key; blank values become None."""
    if musical_key is None:
        return None
    value = musical_key.strip()
    return value or None


def parse_artist_title(filename: str) -> tuple[str, str]:
    """Split a filename stem into (artist, title) without touching storage."""
    stem = Path(filename).name
    stem = Path(stem).stem.strip()
    live = _LIVE_AT_PATTERN.match(stem)
    if live:
        return live.group("artist").strip() or "Unknown Artist", "Live Set"
    parts = _SPLIT_PATTERN.split(stem, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return parts[0].strip(), parts[1].strip()
    title = re.sub(r"_+", " ", stem).strip()
    return "Unknown Artist", title or "Untitled"


def analyze_tags(
    *,
    bpm: float | None = None,
    musical_key: str | None = None,
    genre: str | None = None,
    artist: str | None = None,
    title: str | None = None,
    source_filename: str | None = None,
) -> NormalizedTags:
    """Normalize BPM/key inputs into a stable tag record.

    An explicit ``genre`` wins; otherwise the best BPM hypothesis wins, or
    ``"Unknown"`` when there is no usable signal. Missing artist/title fall
    back to ``source_filename`` parsing, then to neutral defaults.
    """
    clean_bpm = normalize_bpm(bpm)
    clean_key = normalize_key(musical_key)
    scores = score_genres(clean_bpm)
    if genre is not None and genre.strip():
        resolved_genre = genre.strip()
    elif clean_bpm is not None and max(scores.values(), default=0.0) > 0.0:
        resolved_genre = max(scores, key=scores.get)
    else:
        resolved_genre = UNKNOWN_GENRE

    clean_artist = artist.strip() if artist and artist.strip() else None
    clean_title = title.strip() if title and title.strip() else None
    if (clean_artist is None or clean_title is None) and source_filename:
        parsed_artist, parsed_title = parse_artist_title(source_filename)
        clean_artist = clean_artist or parsed_artist
        clean_title = clean_title or parsed_title
    return NormalizedTags(
        bpm=clean_bpm,
        musical_key=clean_key,
        genre=resolved_genre,
        genre_scores=scores,
        artist=clean_artist or "Unknown Artist",
        title=clean_title or "Untitled",
    )


def build_suggested_download_name(
    *,
    artist: str,
    title: str,
    genre: str,
    extension: str = ".wav",
) -> str:
    """Build a normalized presentation name; immutable object keys are untouched."""
    safe = lambda value: _UNSAFE_CHARS_PATTERN.sub("", str(value)).strip()
    suffix = extension if extension.startswith(".") else f".{extension}"
    clean_artist = safe(artist) or "Unknown Artist"
    clean_title = safe(title) or "Untitled"
    clean_genre = safe(genre) or "Neutral"
    return f"{clean_artist} - {clean_title} [{clean_genre}]{suffix}"


__all__ = [
    "GENRE_PROFILES",
    "TAG_ALGORITHM_VERSION",
    "TAG_ARTIFACT_ROLE",
    "UNKNOWN_GENRE",
    "NormalizedTags",
    "analyze_tags",
    "build_suggested_download_name",
    "normalize_bpm",
    "normalize_key",
    "parse_artist_title",
    "score_genres",
]
