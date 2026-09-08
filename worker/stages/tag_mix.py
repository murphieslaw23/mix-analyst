"""Versioned metadata report and presentation-name stage."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from worker.dsp.tagging import TagReport, analyze_audio, suggest_download_name
from worker.stages.generate_waveform import artifact_key


@dataclass(frozen=True)
class Artifact:
    role: str
    key: str
    sha256: str
    algorithm_version: str
    media_type: str
    byte_length: int


@dataclass(frozen=True)
class TaggedMix:
    source_artifact: Artifact
    metadata_artifact: Artifact
    report: TagReport
    suggested_download_name: str
    payload: bytes


def tag_mix(
    source: Path,
    source_artifact: Artifact,
    source_filename: str,
    algorithm_version: str,
) -> TaggedMix:
    """Analyze a source and produce an immutable report, never retagging it in place."""
    report = analyze_audio(source)
    suggested_name = suggest_download_name(
        source_filename, report.genre, Path(source_filename).suffix or ".wav"
    )
    payload = json.dumps(
        {"report": report.as_dict(), "suggested_download_name": suggested_name},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    metadata = Artifact(
        role="metadata",
        key=artifact_key(source_artifact.sha256, "metadata", algorithm_version),
        sha256=hashlib.sha256(payload).hexdigest(),
        algorithm_version=algorithm_version,
        media_type="application/json",
        byte_length=len(payload),
    )
    return TaggedMix(source_artifact, metadata, report, suggested_name, payload)


__all__ = ["Artifact", "TaggedMix", "tag_mix"]
