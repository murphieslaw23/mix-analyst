"""Pure worker DSP primitives (no file IO, no storage access)."""

from worker.dsp.mastering import (
    MASTERING_ALGORITHM_VERSION,
    MasterResult,
    MasterSettings,
    compute_master_gain,
    db_to_linear,
    master_artifact_key,
    peak_ceiling_linear,
)
from worker.dsp.tagging import (
    GENRE_PROFILES,
    TAG_ALGORITHM_VERSION,
    NormalizedTags,
    analyze_tags,
    build_suggested_download_name,
    parse_artist_title,
    score_genres,
)
from worker.dsp.waveforms import WAVEFORM_ALGORITHM_VERSION, compute_waveform

__all__ = [
    "GENRE_PROFILES",
    "MASTERING_ALGORITHM_VERSION",
    "TAG_ALGORITHM_VERSION",
    "WAVEFORM_ALGORITHM_VERSION",
    "MasterResult",
    "MasterSettings",
    "NormalizedTags",
    "analyze_tags",
    "build_suggested_download_name",
    "compute_master_gain",
    "compute_waveform",
    "db_to_linear",
    "master_artifact_key",
    "parse_artist_title",
    "peak_ceiling_linear",
    "score_genres",
]
