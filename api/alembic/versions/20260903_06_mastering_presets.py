"""seed builtin mastering presets

Revision ID: 20260903_06_mastering_presets
Revises: 20260903_05_artifacts

MasteringJob.preset_id references mastering_presets.id, but nothing ever
inserted the builtin rows: on Postgres (which enforces foreign keys,
unlike SQLite test doubles) every mastering trigger died at commit.
This seeds the builtins idempotently; values mirror
worker.analysis.mastering_engine.DEFAULT_PRESETS.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_06_mastering_presets"
down_revision: str | Sequence[str] | None = "20260903_05_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BUILTIN_PRESETS = [
    {
        "id": "sound_system_heavy",
        "name": "Sound System Heavy",
        "description": "Heavy sub bass enhancement, tight dynamics, and loud club master.",
        "target_lufs": -11.0,
        "true_peak_ceiling": -0.8,
        "target_lra": 6.0,
        "eq_settings": {"sub_boost_db": 2.5, "high_air_db": 1.5, "mud_cut_db": -1.5},
        "compressor_settings": {
            "threshold_db": -16.0,
            "ratio": 3.0,
            "attack_ms": 20.0,
            "release_ms": 100.0,
        },
    },
    {
        "id": "club_broadcast",
        "name": "Club Broadcast",
        "description": "Balanced streaming and broadcast profile complying with EBU R128.",
        "target_lufs": -14.0,
        "true_peak_ceiling": -1.0,
        "target_lra": 7.0,
        "eq_settings": {"sub_boost_db": 1.0, "high_air_db": 1.0, "mud_cut_db": -1.0},
        "compressor_settings": {
            "threshold_db": -18.0,
            "ratio": 2.5,
            "attack_ms": 30.0,
            "release_ms": 120.0,
        },
    },
    {
        "id": "vinyl_premaster",
        "name": "Vinyl Pre-Master",
        "description": "High dynamic range with high-pass rumble filter and conservative ceiling.",
        "target_lufs": -16.0,
        "true_peak_ceiling": -1.5,
        "target_lra": 9.0,
        "eq_settings": {"sub_boost_db": 0.0, "high_air_db": 0.5, "mud_cut_db": -0.5},
        "compressor_settings": {
            "threshold_db": -22.0,
            "ratio": 2.0,
            "attack_ms": 40.0,
            "release_ms": 150.0,
        },
    },
]


def upgrade() -> None:
    for preset in BUILTIN_PRESETS:
        op.execute(
            sa.text("""
                INSERT INTO mastering_presets (
                    id, name, description, target_lufs, true_peak_ceiling,
                    target_lra, eq_settings, compressor_settings, is_builtin
                ) VALUES (
                    :id, :name, :description, :lufs, :ceiling,
                    :lra, :eq, :comp, TRUE
                ) ON CONFLICT (id) DO NOTHING
            """).bindparams(
                id=preset["id"],
                name=preset["name"],
                description=preset["description"],
                lufs=preset["target_lufs"],
                ceiling=preset["true_peak_ceiling"],
                lra=preset["target_lra"],
                eq=json.dumps(preset["eq_settings"]),
                comp=json.dumps(preset["compressor_settings"]),
            )
        )


def downgrade() -> None:
    for preset in BUILTIN_PRESETS:
        op.execute(
            sa.text(
                "DELETE FROM mastering_presets WHERE id = :id AND is_builtin = TRUE"
            ).bindparams(id=preset["id"])
        )
