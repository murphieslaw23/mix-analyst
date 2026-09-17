"""identity ownership scope

Revision ID: 20260903_03_identity_scope
Revises: 20260903_02_outbox_events
Create Date: 2026-09-17

Users/projects own every media, job, upload and notification row.
Existing rows are backfilled to the default appliance project.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_03_identity_scope"
down_revision: str | Sequence[str] | None = "20260903_02_outbox_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_USER_ID = "default-user"
DEFAULT_PROJECT_ID = "default-project"

OWNED_TABLES = ("jobs", "media_assets", "mixes", "upload_sessions")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"], unique=False)

    # Bootstrap the appliance identity before any FK references it, so
    # pre-existing rows backfill to a project that actually exists.
    op.execute(
        sa.text(
            "INSERT INTO users (id, created_at) VALUES (:id, CURRENT_TIMESTAMP)"
        ).bindparams(id=DEFAULT_USER_ID)
    )
    op.execute(
        sa.text(
            "INSERT INTO projects (id, owner_id, created_at) VALUES (:id, :owner, CURRENT_TIMESTAMP)"
        ).bindparams(id=DEFAULT_PROJECT_ID, owner=DEFAULT_USER_ID)
    )

    for table in OWNED_TABLES:
        # Explicit batch blocks: SQLite cannot ALTER constraints, so the
        # dialect transparently uses copy-and-move there.
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "project_id",
                    sa.String(length=36),
                    nullable=False,
                    server_default=DEFAULT_PROJECT_ID,
                )
            )
            batch_op.create_index(f"ix_{table}_project_id", ["project_id"])
            batch_op.create_foreign_key(
                f"fk_{table}_project_id", "projects", ["project_id"], ["id"]
            )


def downgrade() -> None:
    for table in reversed(OWNED_TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_project_id", type_="foreignkey")
            batch_op.drop_index(f"ix_{table}_project_id")
            batch_op.drop_column("project_id")
    op.execute(
        sa.text("DELETE FROM projects WHERE id = :id").bindparams(id=DEFAULT_PROJECT_ID)
    )
    op.execute(
        sa.text("DELETE FROM users WHERE id = :id").bindparams(id=DEFAULT_USER_ID)
    )
    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("users")
