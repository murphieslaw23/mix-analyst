"""Deterministic loudness mastering primitives for the worker runtime."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ALGORITHM_VERSION = "v1"
_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class MasterSettings:
    """Stable settings for one immutable mastering execution."""

    target_lufs: float = -9.0
    true_peak_dbtp: float = -1.0
    project_id: str = "local"
    storage_root: Path | None = None
    algorithm_version: str = ALGORITHM_VERSION

    def __post_init__(self) -> None:
        if not -36.0 <= self.target_lufs <= -3.0:
            raise ValueError("target_lufs must be between -36 and -3")
        if not -12.0 <= self.true_peak_dbtp <= 0.0:
            raise ValueError("true_peak_dbtp must be between -12 and 0")
        if not _KEY_SEGMENT.fullmatch(self.project_id):
            raise ValueError("project_id contains an unsafe object-key segment")
        if not _KEY_SEGMENT.fullmatch(self.algorithm_version):
            raise ValueError("algorithm_version contains an unsafe object-key segment")


@dataclass(frozen=True)
class MasterResult:
    artifact_key: str
    integrated_lufs: float
    true_peak_dbtp: float
    algorithm_version: str


def _integrated_lufs(audio: np.ndarray, sample_rate: int) -> float:
    import pyloudnorm as pyln

    loudness = float(pyln.Meter(sample_rate).integrated_loudness(np.asarray(audio, dtype=np.float64)))
    if not np.isfinite(loudness):
        raise ValueError("audio has no measurable integrated loudness")
    return loudness


def _true_peak_dbtp(audio: np.ndarray) -> float:
    """Measure a deterministic 4x oversampled peak estimate."""
    from scipy.signal import resample_poly

    samples = np.asarray(audio, dtype=np.float64)
    oversampled = resample_poly(samples, up=4, down=1, axis=0)
    peak = float(np.max(np.abs(oversampled))) if oversampled.size else 0.0
    return 20.0 * np.log10(max(peak, 1e-12))


def _master_audio(audio: np.ndarray, sample_rate: int, settings: MasterSettings) -> np.ndarray:
    samples = np.asarray(audio, dtype=np.float64)
    if samples.size == 0:
        raise ValueError("audio is empty")

    input_lufs = _integrated_lufs(samples, sample_rate)
    normalized = samples * (10.0 ** ((settings.target_lufs - input_lufs) / 20.0))
    true_peak = _true_peak_dbtp(normalized)
    if true_peak > settings.true_peak_dbtp:
        normalized *= 10.0 ** ((settings.true_peak_dbtp - true_peak) / 20.0)
    return np.clip(normalized, -1.0, 1.0).astype(np.float32)


def _object_key(project_id: str, content_hash: str, algorithm_version: str) -> str:
    return f"projects/{project_id}/artifacts/mastered/{algorithm_version}/{content_hash}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as payload:
        while chunk := payload.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def master_audio_file(source_path: Path, settings: MasterSettings) -> MasterResult:
    """Master a trusted worker-local source and link it once at an opaque key.

    The caller supplies a storage root only inside the worker. API callers never
    receive or choose local paths; they receive the returned object key instead.
    """
    import soundfile as sf

    source = Path(source_path).resolve()
    if not source.is_file():
        raise FileNotFoundError("mastering source artifact does not exist")
    storage_root = (settings.storage_root or source.parent).resolve()
    try:
        source.relative_to(storage_root)
    except ValueError as exc:
        raise ValueError("mastering source is outside the trusted storage root") from exc

    audio, sample_rate = sf.read(source, always_2d=False, dtype="float32")
    mastered = _master_audio(audio, int(sample_rate), settings)
    final_lufs = _integrated_lufs(mastered, int(sample_rate))
    final_peak = _true_peak_dbtp(mastered)

    staging_dir = storage_root / ".staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix="master-", suffix=".wav", dir=staging_dir)
    temporary = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            sf.write(handle, mastered, int(sample_rate), format="WAV", subtype="PCM_24")
            handle.flush()
            os.fsync(handle.fileno())
        object_key = _object_key(settings.project_id, _sha256(temporary), settings.algorithm_version)
        destination = storage_root / object_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            # A retry produced identical bytes. Keep the already-immutable object.
            pass
    finally:
        if temporary.exists():
            temporary.unlink()

    return MasterResult(
        artifact_key=object_key,
        integrated_lufs=float(round(final_lufs, 2)),
        true_peak_dbtp=float(round(final_peak, 2)),
        algorithm_version=settings.algorithm_version,
    )
