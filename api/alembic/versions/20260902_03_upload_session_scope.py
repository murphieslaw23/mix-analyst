"""Scope existing upload sessions to projects.

Revision ID: 20260902_03
Revises: 20260902_02
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_03"
down_revision: Union[str, Sequence[str], None] = "20260902_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LEGACY_PROJECT_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    with op.batch_alter_table("upload_sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "project_id",
                sa.String(length=36),
                nullable=False,
                server_default=LEGACY_PROJECT_ID,
            )
        )
        batch_op.create_foreign_key(
            "fk_upload_sessions_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
        )
        batch_op.create_index("ix_upload_sessions_project_id", ["project_id"])
        batch_op.alter_column("project_id", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("upload_sessions") as batch_op:
        batch_op.drop_index("ix_upload_sessions_project_id")
        batch_op.drop_constraint("fk_upload_sessions_project_id_projects", type_="foreignkey")
        batch_op.drop_column("project_id")
