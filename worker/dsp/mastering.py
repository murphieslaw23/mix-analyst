"""Deterministic loudness mastering primitives for the worker runtime."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import numpy as np


ALGORITHM_VERSION = "v1"
_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_IN_MEMORY_SECONDS = 8.0


@dataclass(frozen=True)
class MasterSettings:
    """Stable settings for one immutable mastering execution."""

    target_lufs: float = -9.0
    true_peak_dbtp: float = -1.0
    target_lra: float = 7.0
    eq_settings: Mapping[str, float] = field(default_factory=dict)
    compressor_settings: Mapping[str, float] = field(default_factory=dict)
    project_id: str = "local"
    storage_root: Path | None = None
    algorithm_version: str = ALGORITHM_VERSION

    def __post_init__(self) -> None:
        if not -36.0 <= self.target_lufs <= -3.0:
            raise ValueError("target_lufs must be between -36 and -3")
        if not -12.0 <= self.true_peak_dbtp <= 0.0:
            raise ValueError("true_peak_dbtp must be between -12 and 0")
        if not 1.0 <= self.target_lra <= 30.0:
            raise ValueError("target_lra must be between 1 and 30")
        _validated_eq_settings(self.eq_settings)
        _validated_compressor_settings(self.compressor_settings)
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
    """Measure a deterministic 4x oversampled peak estimate for capped arrays."""
    from scipy.signal import resample_poly

    samples = np.asarray(audio, dtype=np.float64)
    oversampled = resample_poly(samples, up=4, down=1, axis=0)
    peak = float(np.max(np.abs(oversampled))) if oversampled.size else 0.0
    return 20.0 * np.log10(max(peak, 1e-12))


def _validated_eq_settings(settings: Mapping[str, float]) -> dict[str, float]:
    allowed = {"sub_boost_db", "mud_cut_db", "high_air_db"}
    unknown = set(settings) - allowed
    if unknown:
        raise ValueError(f"unsupported EQ setting(s): {', '.join(sorted(unknown))}")
    result = {key: float(value) for key, value in settings.items()}
    if any(not -12.0 <= value <= 12.0 for value in result.values()):
        raise ValueError("EQ gains must be between -12 and 12 dB")
    return result


def _validated_compressor_settings(settings: Mapping[str, float]) -> dict[str, float]:
    allowed = {"threshold_db", "ratio", "attack_ms", "release_ms"}
    unknown = set(settings) - allowed
    if unknown:
        raise ValueError(f"unsupported compressor setting(s): {', '.join(sorted(unknown))}")
    result = {key: float(value) for key, value in settings.items()}
    if "threshold_db" in result and not -60.0 <= result["threshold_db"] <= 0.0:
        raise ValueError("compressor threshold must be between -60 and 0 dB")
    if "ratio" in result and not 1.0 <= result["ratio"] <= 20.0:
        raise ValueError("compressor ratio must be between 1 and 20")
    for key in ("attack_ms", "release_ms"):
        if key in result and not 0.1 <= result[key] <= 2000.0:
            raise ValueError(f"compressor {key} must be between 0.1 and 2000 ms")
    return result


def _apply_profile_eq(audio: np.ndarray, sample_rate: int, settings: Mapping[str, float]) -> np.ndarray:
    """Apply the deterministic reference EQ to a bounded in-memory signal."""
    controls = _validated_eq_settings(settings)
    if not controls:
        return np.asarray(audio, dtype=np.float64)
    samples = np.asarray(audio, dtype=np.float64)
    sample_count = samples.shape[0]
    frequencies = np.fft.rfftfreq(sample_count, d=1.0 / sample_rate)
    safe_frequency = np.maximum(frequencies, 1.0)
    sub = controls.get("sub_boost_db", 0.0) * np.exp(-0.5 * (np.log2(safe_frequency / 65.0) / 0.9) ** 2)
    mud = controls.get("mud_cut_db", 0.0) * np.exp(-0.5 * (np.log2(safe_frequency / 300.0) / 0.85) ** 2)
    air = controls.get("high_air_db", 0.0) / (1.0 + np.exp(-(frequencies - 9000.0) / 1600.0))
    gain = 10.0 ** ((sub + mud + air) / 20.0)
    spectrum = np.fft.rfft(samples, axis=0)
    if samples.ndim == 1:
        spectrum *= gain
    else:
        spectrum *= gain[:, np.newaxis]
    return np.fft.irfft(spectrum, n=sample_count, axis=0)


def _apply_profile_compression(
    audio: np.ndarray,
    sample_rate: int,
    target_lra: float,
    settings: Mapping[str, float],
) -> np.ndarray:
    """Apply linked-stereo reference compression to a bounded signal."""
    controls = _validated_compressor_settings(settings)
    threshold_db = controls.get("threshold_db", -18.0)
    ratio = max(controls.get("ratio", 2.0), 1.0 + (12.0 - min(target_lra, 12.0)) / 6.0)
    attack_ms = controls.get("attack_ms", 20.0)
    release_ms = controls.get("release_ms", 120.0)
    samples = np.asarray(audio, dtype=np.float64)
    linked = np.max(np.abs(samples), axis=1) if samples.ndim > 1 else np.abs(samples)
    level_db = 20.0 * np.log10(np.maximum(linked, 1e-12))
    desired_reduction = np.minimum(
        0.0,
        threshold_db + np.maximum(level_db - threshold_db, 0.0) / ratio - level_db,
    )
    envelope = np.empty_like(desired_reduction)
    envelope[0] = desired_reduction[0]
    attack = np.exp(-1.0 / max(1.0, sample_rate * attack_ms / 1000.0))
    release = np.exp(-1.0 / max(1.0, sample_rate * release_ms / 1000.0))
    for index in range(1, len(desired_reduction)):
        coefficient = attack if desired_reduction[index] < envelope[index - 1] else release
        envelope[index] = coefficient * envelope[index - 1] + (1.0 - coefficient) * desired_reduction[index]
    gain = 10.0 ** (envelope / 20.0)
    return samples * (gain[:, np.newaxis] if samples.ndim > 1 else gain)


def _master_audio(audio: np.ndarray, sample_rate: int, settings: MasterSettings) -> np.ndarray:
    samples = np.asarray(audio, dtype=np.float64)
    if samples.size == 0:
        raise ValueError("audio is empty")
    profiled = _apply_profile_eq(samples, sample_rate, settings.eq_settings)
    profiled = _apply_profile_compression(profiled, sample_rate, settings.target_lra, settings.compressor_settings)
    input_lufs = _integrated_lufs(profiled, sample_rate)
    normalized = profiled * (10.0 ** ((settings.target_lufs - input_lufs) / 20.0))
    true_peak = _true_peak_dbtp(normalized)
    if true_peak > settings.true_peak_dbtp:
        normalized *= 10.0 ** ((settings.true_peak_dbtp - true_peak) / 20.0)
    return np.clip(normalized, -1.0, 1.0).astype(np.float32)


def _profile_filters(settings: MasterSettings) -> list[str]:
    """Translate validated profile controls to streaming FFmpeg filters."""
    eq = _validated_eq_settings(settings.eq_settings)
    compressor = _validated_compressor_settings(settings.compressor_settings)
    filters: list[str] = []
    if eq.get("sub_boost_db", 0.0):
        filters.append(f"bass=g={eq['sub_boost_db']:.6f}:f=65")
    if eq.get("mud_cut_db", 0.0):
        filters.append(f"equalizer=f=300:t=q:w=1:g={eq['mud_cut_db']:.6f}")
    if eq.get("high_air_db", 0.0):
        filters.append(f"treble=g={eq['high_air_db']:.6f}:f=9000")
    threshold_db = compressor.get("threshold_db", -18.0)
    ratio = max(compressor.get("ratio", 2.0), 1.0 + (12.0 - min(settings.target_lra, 12.0)) / 6.0)
    attack_ms = compressor.get("attack_ms", 20.0)
    release_ms = compressor.get("release_ms", 120.0)
    threshold_linear = 10.0 ** (threshold_db / 20.0)
    filters.append(
        "acompressor="
        f"threshold={threshold_linear:.8f}:ratio={ratio:.6f}:"
        f"attack={attack_ms:.6f}:release={release_ms:.6f}:link=maximum"
    )
    return filters


def _extract_loudnorm_json(stderr: str) -> dict[str, str]:
    start = stderr.rfind("{\n")
    end = stderr.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("FFmpeg loudness measurement did not return JSON")
    try:
        payload = json.loads(stderr[start : end + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError("FFmpeg loudness measurement returned invalid JSON") from exc
    return {str(key): str(value) for key, value in payload.items()}


def _run_ffmpeg_measure(source: Path, filters: list[str], settings: MasterSettings) -> dict[str, str]:
    loudnorm = f"loudnorm=I={settings.target_lufs}:TP={settings.true_peak_dbtp}:LRA={settings.target_lra}:print_format=json"
    chain = ",".join([*filters, loudnorm])
    completed = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-v", "info", "-i", str(source), "-af", chain, "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"FFmpeg mastering measurement failed: {completed.stderr[-1200:]}")
    return _extract_loudnorm_json(completed.stderr)


def _stream_master_audio(source: Path, destination: Path, settings: MasterSettings) -> tuple[float, float]:
    """Two-pass FFmpeg mastering; decoded PCM remains inside bounded pipes."""
    filters = _profile_filters(settings)
    measured = _run_ffmpeg_measure(source, filters, settings)
    required = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if any(key not in measured for key in required):
        raise RuntimeError("FFmpeg loudness measurement omitted required fields")
    loudnorm = (
        f"loudnorm=I={settings.target_lufs}:TP={settings.true_peak_dbtp}:LRA={settings.target_lra}:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true:print_format=summary"
    )
    chain = ",".join([*filters, loudnorm])
    completed = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-v", "error", "-y", "-i", str(source),
            "-af", chain, "-c:a", "pcm_s24le", str(destination),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"FFmpeg mastering render failed: {completed.stderr[-1200:]}")
    final = _run_ffmpeg_measure(destination, [], settings)
    try:
        return float(final["input_i"]), float(final["input_tp"])
    except (KeyError, ValueError) as exc:
        raise RuntimeError("FFmpeg final loudness measurement was incomplete") from exc


def _object_key(project_id: str, content_hash: str, algorithm_version: str) -> str:
    return f"projects/{project_id}/artifacts/mastered/{algorithm_version}/{content_hash}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as payload:
        while chunk := payload.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def master_audio_file(source_path: Path, settings: MasterSettings) -> MasterResult:
    """Master a trusted source with a bounded-memory long-form production path."""
    import soundfile as sf

    source = Path(source_path).resolve()
    if not source.is_file():
        raise FileNotFoundError("mastering source artifact does not exist")
    storage_root = (settings.storage_root or source.parent).resolve()
    try:
        source.relative_to(storage_root)
    except ValueError as exc:
        raise ValueError("mastering source is outside the trusted storage root") from exc

    info = sf.info(source)
    if info.frames <= 0 or info.samplerate <= 0:
        raise ValueError("audio is empty")
    staging_dir = storage_root / ".staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix="master-", suffix=".wav", dir=staging_dir)
    temporary = Path(temp_name)
    os.close(descriptor)
    try:
        if info.frames <= int(info.samplerate * MAX_IN_MEMORY_SECONDS):
            audio, sample_rate = sf.read(source, always_2d=False, dtype="float32")
            mastered = _master_audio(audio, int(sample_rate), settings)
            sf.write(temporary, mastered, int(sample_rate), format="WAV", subtype="PCM_24")
            final_lufs = _integrated_lufs(mastered, int(sample_rate))
            final_peak = _true_peak_dbtp(mastered)
        else:
            final_lufs, final_peak = _stream_master_audio(source, temporary, settings)

        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        object_key = _object_key(settings.project_id, _sha256(temporary), settings.algorithm_version)
        destination = storage_root / object_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(temporary, destination)
        except FileExistsError:
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
