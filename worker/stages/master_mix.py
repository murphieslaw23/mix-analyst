"""Immutable master-mix stage contract."""

from pathlib import Path

from worker.dsp.mastering import MasterResult, MasterSettings, master_audio_file


def run_master_mix(source_path: Path, settings: MasterSettings) -> MasterResult:
    """Produce one deterministic mastered object and its durable report values."""
    return master_audio_file(source_path, settings)


__all__ = ["MasterResult", "MasterSettings", "run_master_mix"]
