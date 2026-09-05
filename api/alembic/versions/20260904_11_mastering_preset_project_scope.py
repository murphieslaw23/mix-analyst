"""Scope mutable mastering presets to a project.

Revision ID: 20260904_11_mastering_preset_project_scope
Revises: 20260903_10_final_core_repair
Create Date: 2026-09-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_11_mastering_preset_project_scope"
down_revision: Union[str, Sequence[str], None] = "20260903_10_final_core_repair"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("mastering_presets") as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_mastering_presets_project_id_projects", "projects", ["project_id"], ["id"]
        )
        batch_op.create_index("ix_mastering_presets_project_id", ["project_id"])


def downgrade() -> None:
    with op.batch_alter_table("mastering_presets") as batch_op:
        batch_op.drop_index("ix_mastering_presets_project_id")
        batch_op.drop_constraint("fk_mastering_presets_project_id_projects", type_="foreignkey")
        batch_op.drop_column("project_id")
