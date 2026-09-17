"""Versioned metadata/tag artifact stage.

File IO lives here: hash the source bytes, normalize the caller-supplied
BPM/key inputs through ``worker.dsp.tagging`` pure functions, and persist one
canonical JSON report to ``dest``. The source object is never renamed or
mutated; only a suggested download name is produced for presentation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from worker.dsp.tagging import (
    TAG_ALGORITHM_VERSION,
    TAG_ARTIFACT_ROLE,
    NormalizedTags,
    analyze_tags,
    build_suggested_download_name,
)


@dataclass(frozen=True)
class TagMixResult:
    """Immutable metadata report identity for one tagged source."""

    artifact_key: str
    sha256: str
    algorithm_version: str
    media_type: str
    byte_length: int
    suggested_download_name: str
    tags: NormalizedTags


def tag_artifact_key(
    source_sha256: str,
    algorithm_version: str = TAG_ALGORITHM_VERSION,
) -> str:
    """Return the immutable storage key for a metadata report payload."""
    if not source_sha256:
        raise ValueError("source_sha256 must not be empty")
    if not algorithm_version:
        raise ValueError("algorithm_version must not be empty")
    return f"artifacts/{TAG_ARTIFACT_ROLE}/{algorithm_version}/{source_sha256}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def tag_mix(
    source: Path,
    dest: Path,
    *,
    bpm: float | None = None,
    musical_key: str | None = None,
    genre: str | None = None,
    artist: str | None = None,
    title: str | None = None,
    source_filename: str | None = None,
    extension: str | None = None,
    algorithm_version: str = TAG_ALGORITHM_VERSION,
) -> TagMixResult:
    """Analyze tag inputs for ``source`` and persist the JSON report to ``dest``."""
    if not algorithm_version:
        raise ValueError("algorithm_version must not be empty")
    src = Path(source)
    dst = Path(dest)
    if not src.is_file():
        raise FileNotFoundError("tag source artifact does not exist")

    tags = analyze_tags(
        bpm=bpm,
        musical_key=musical_key,
        genre=genre,
        artist=artist,
        title=title,
        source_filename=source_filename or src.name,
    )
    resolved_extension = extension or Path(source_filename or src.name).suffix or ".wav"
    suggested_name = build_suggested_download_name(
        artist=tags.artist,
        title=tags.title,
        genre=tags.genre,
        extension=resolved_extension,
    )
    payload = json.dumps(
        {"suggested_download_name": suggested_name, "tags": tags.as_dict()},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(payload)
    return TagMixResult(
        artifact_key=tag_artifact_key(_sha256(src), algorithm_version),
        sha256=hashlib.sha256(payload).hexdigest(),
        algorithm_version=algorithm_version,
        media_type="application/json",
        byte_length=len(payload),
        suggested_download_name=suggested_name,
        tags=tags,
    )


__all__ = ["TagMixResult", "tag_artifact_key", "tag_mix"]
