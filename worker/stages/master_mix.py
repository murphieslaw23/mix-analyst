"""Immutable master-mix artifact stage.

File IO lives here: measure the source with
``worker.analysis.loudness_analyzer.measure_program_loudness``, stream
block-wise gain plus true-peak clipping (adapted from the mastering pipeline
in ``worker.tasks``) into ``dest``, then measure the mastered file and return
a content-addressed :class:`MasterResult`. Pure gain/ceiling math and key
shaping come from ``worker.dsp.mastering``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import soundfile as sf

from worker.analysis.loudness_analyzer import measure_program_loudness
from worker.dsp.mastering import (
    MASTERING_ALGORITHM_VERSION,
    MasterResult,
    MasterSettings,
    compute_master_gain,
    db_to_linear,
    master_artifact_key,
    peak_ceiling_linear,
)

_STREAM_BLOCKSIZE = 65536


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def master_mix(
    source: Path,
    dest: Path,
    settings: MasterSettings | None = None,
) -> MasterResult:
    """Master ``source`` into ``dest`` and return its immutable measurement."""
    active = settings if settings is not None else MasterSettings()
    src = Path(source)
    dst = Path(dest)
    if not src.is_file():
        raise FileNotFoundError("mastering source artifact does not exist")

    input_metrics = measure_program_loudness(src)
    gain_lin = db_to_linear(
        compute_master_gain(float(input_metrics["integrated_lufs"]), active)
    )
    ceiling_lin = peak_ceiling_linear(active)

    dst.parent.mkdir(parents=True, exist_ok=True)
    with (
        sf.SoundFile(str(src), "r") as fin,
        sf.SoundFile(
            str(dst),
            "w",
            samplerate=fin.samplerate,
            channels=fin.channels,
            subtype="PCM_16",
        ) as fout,
    ):
        for block in fin.blocks(
            blocksize=_STREAM_BLOCKSIZE, dtype="float32", always_2d=True
        ):
            fout.write(np.clip(block * gain_lin, -ceiling_lin, ceiling_lin))

    output_metrics = measure_program_loudness(dst)
    return MasterResult(
        artifact_key=master_artifact_key(_sha256(dst)),
        integrated_lufs=round(float(output_metrics["integrated_lufs"]), 2),
        true_peak_dbtp=round(float(output_metrics["true_peak_db"]), 2),
        algorithm_version=MASTERING_ALGORITHM_VERSION,
    )


__all__ = ["master_mix"]
