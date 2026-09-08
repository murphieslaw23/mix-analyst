"""Add user-owned projects and project scope for media, mixes, and jobs.

Revision ID: 20260902_02
Revises: 20260902_01
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_02"
down_revision: str | Sequence[str] | None = "20260902_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LEGACY_USER_ID = "00000000-0000-0000-0000-000000000001"
LEGACY_PROJECT_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])

    # Preserve access to pre-identity rows by assigning them to a single legacy
    # project. New application writes supply a principal project explicitly.
    op.bulk_insert(
        sa.table("users", sa.column("id", sa.String(length=36))),
        [{"id": LEGACY_USER_ID}],
    )
    op.bulk_insert(
        sa.table(
            "projects",
            sa.column("id", sa.String(length=36)),
            sa.column("owner_id", sa.String(length=36)),
        ),
        [{"id": LEGACY_PROJECT_ID, "owner_id": LEGACY_USER_ID}],
    )

    for table_name in ("media_assets", "mixes", "jobs"):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "project_id",
                    sa.String(length=36),
                    nullable=False,
                    server_default=LEGACY_PROJECT_ID,
                )
            )
            batch_op.create_foreign_key(
                f"fk_{table_name}_project_id_projects",
                "projects",
                ["project_id"],
                ["id"],
            )
            batch_op.create_index(f"ix_{table_name}_project_id", ["project_id"])
            batch_op.alter_column("project_id", server_default=None)


def downgrade() -> None:
    for table_name in ("jobs", "mixes", "media_assets"):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_index(f"ix_{table_name}_project_id")
            batch_op.drop_constraint(
                f"fk_{table_name}_project_id_projects", type_="foreignkey"
            )
            batch_op.drop_column("project_id")

    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("users")
