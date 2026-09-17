"""Builtin mastering preset bootstrap.

MasteringJob.preset_id references mastering_presets.id, so the builtin
rows must exist wherever jobs are created: the Alembic seed migration
covers deployed databases, and ensure_builtin_presets covers fresh
ones (tests, first boot ordering). Idempotent by primary key.
"""

from sqlalchemy.orm import Session

from ..models.mastering import MasteringPreset


def ensure_builtin_presets(db: Session) -> int:
    """Insert missing builtin presets; returns the number created."""
    from worker.analysis.mastering_engine import DEFAULT_PRESETS

    created = 0
    for key, preset in DEFAULT_PRESETS.items():
        if db.get(MasteringPreset, key) is None:
            db.add(
                MasteringPreset(
                    id=key,
                    name=preset["name"],
                    description=preset.get("description"),
                    target_lufs=preset["target_lufs"],
                    true_peak_ceiling=preset["true_peak_ceiling"],
                    target_lra=preset["target_lra"],
                    eq_settings=preset["eq_settings"],
                    compressor_settings=preset["compressor_settings"],
                    is_builtin=True,
                )
            )
            created += 1
    if created:
        db.commit()
    return created
