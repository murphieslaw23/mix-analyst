"""Scope mutable mastering presets to a project.

Revision ID: 20260904_11_mastering_preset_project_scope
Revises: 20260903_10_final_core_repair
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_11_mastering_preset_project_scope"
down_revision: str | Sequence[str] | None = "20260903_10_final_core_repair"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("mastering_presets") as batch_op:
        batch_op.add_column(
            sa.Column("project_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "is_legacy_shared",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # The original schema had no preset owner. First scope the records for
    # which history proves one owner: a custom preset used only with media in
    # one project. Anything unreferenced or used from multiple projects was
    # globally visible before this migration, so it stays *explicitly* legacy
    # shared instead of silently assigning it to a tenant we cannot prove.
    # ``IS TRUE``/``IS FALSE`` are accepted by both PostgreSQL and SQLite.
    # Integer boolean comparisons (``= 0``/``= 1``) are rejected by
    # PostgreSQL, even though SQLite happens to accept them.
    op.execute(
        "UPDATE mastering_presets SET is_builtin = FALSE WHERE is_builtin IS NULL"
    )
    op.execute(
        """
        UPDATE mastering_presets
        SET project_id = (
            SELECT MIN(media_assets.project_id)
            FROM mastering_jobs
            JOIN media_assets ON media_assets.id = mastering_jobs.media_id
            WHERE mastering_jobs.preset_id = mastering_presets.id
        )
        WHERE is_builtin IS FALSE
          AND 1 = (
            SELECT COUNT(DISTINCT media_assets.project_id)
            FROM mastering_jobs
            JOIN media_assets ON media_assets.id = mastering_jobs.media_id
            WHERE mastering_jobs.preset_id = mastering_presets.id
          )
        """
    )
    op.execute(
        """
        UPDATE mastering_presets
        SET is_legacy_shared = TRUE
        WHERE is_builtin IS FALSE AND project_id IS NULL
        """
    )

    with op.batch_alter_table("mastering_presets") as batch_op:
        batch_op.alter_column(
            "is_builtin",
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        )
        batch_op.create_foreign_key(
            "fk_mastering_presets_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
        )
        batch_op.create_index("ix_mastering_presets_project_id", ["project_id"])
        batch_op.create_check_constraint(
            "ck_mastering_presets_owner_or_global",
            "is_builtin IS TRUE OR is_legacy_shared IS TRUE OR project_id IS NOT NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("mastering_presets") as batch_op:
        batch_op.drop_constraint("ck_mastering_presets_owner_or_global", type_="check")
        batch_op.drop_index("ix_mastering_presets_project_id")
        batch_op.drop_constraint(
            "fk_mastering_presets_project_id_projects", type_="foreignkey"
        )
        batch_op.drop_column("is_legacy_shared")
        batch_op.drop_column("project_id")
