"""Resolve explicit mastering profiles without crossing project boundaries."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models.mastering import MasteringPreset
from ..schemas.auth import CurrentPrincipal

# Versioned, server-owned built-ins do not need a mutable database row. The
# selected identifier and all effective values are persisted on the Job so a
# queued master remains reproducible if a later release changes these defaults.
BUILTIN_PRESETS: dict[str, dict] = {
    "sound_system_heavy": {
        "preset_id": "sound_system_heavy",
        "preset_name": "Sound System Heavy",
        "target_lufs": -11.0,
        "true_peak_dbtp": -0.8,
        "target_lra": 6.0,
        "eq_settings": {"sub_boost_db": 2.5, "high_air_db": 1.5, "mud_cut_db": -1.5},
        "compressor_settings": {
            "threshold_db": -16.0,
            "ratio": 3.0,
            "attack_ms": 20.0,
            "release_ms": 100.0,
        },
    },
    "club_broadcast": {
        "preset_id": "club_broadcast",
        "preset_name": "Club Broadcast",
        "target_lufs": -14.0,
        "true_peak_dbtp": -1.0,
        "target_lra": 7.0,
        "eq_settings": {"sub_boost_db": 1.0, "high_air_db": 1.0, "mud_cut_db": -1.0},
        "compressor_settings": {
            "threshold_db": -18.0,
            "ratio": 2.5,
            "attack_ms": 30.0,
            "release_ms": 120.0,
        },
    },
    "vinyl_premaster": {
        "preset_id": "vinyl_premaster",
        "preset_name": "Vinyl Pre-Master",
        "target_lufs": -16.0,
        "true_peak_dbtp": -1.5,
        "target_lra": 9.0,
        "eq_settings": {"sub_boost_db": 0.0, "high_air_db": 0.5, "mud_cut_db": -0.5},
        "compressor_settings": {
            "threshold_db": -22.0,
            "ratio": 2.0,
            "attack_ms": 40.0,
            "release_ms": 150.0,
        },
    },
}


def resolve_mastering_parameters(
    db: Session,
    principal: CurrentPrincipal,
    preset_id: str | None,
    *,
    target_lufs: float | None,
    true_peak_dbtp: float | None,
) -> dict:
    """Load a built-in or project-owned preset and persist effective settings."""
    selected_id = preset_id or "sound_system_heavy"
    builtin = BUILTIN_PRESETS.get(selected_id)
    if builtin is not None:
        parameters = {**builtin}
    else:
        preset = db.scalar(
            select(MasteringPreset).where(
                MasteringPreset.id == selected_id,
                or_(
                    MasteringPreset.is_builtin.is_(True),
                    MasteringPreset.is_legacy_shared.is_(True),
                    MasteringPreset.project_id == principal.project_id,
                ),
            )
        )
        if preset is None:
            # Keep a foreign project's identifier non-enumerable.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mastering preset not found",
            )
        parameters = {
            "preset_id": preset.id,
            "preset_name": preset.name,
            "target_lufs": preset.target_lufs,
            "true_peak_dbtp": preset.true_peak_ceiling,
            "target_lra": preset.target_lra,
            "eq_settings": preset.eq_settings or {},
            "compressor_settings": preset.compressor_settings or {},
        }

    if target_lufs is not None:
        parameters["target_lufs"] = target_lufs
    if true_peak_dbtp is not None:
        parameters["true_peak_dbtp"] = true_peak_dbtp
    parameters["algorithm_version"] = "v1"
    return parameters
