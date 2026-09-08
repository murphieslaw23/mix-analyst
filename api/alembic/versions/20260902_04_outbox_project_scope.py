"""Scope existing durable outbox commands to their authoritative job project.

Revision ID: 20260902_04_outbox_project_scope
Revises: 20260902_04_outbox_attempts
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_04_outbox_project_scope"
down_revision: str | Sequence[str] | None = "20260902_04_outbox_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("outbox_messages") as batch_op:
        batch_op.add_column(
            sa.Column("project_id", sa.String(length=36), nullable=True)
        )

    # Every Task 4 outbox aggregate is a job. Backfill from that authoritative
    # owner before making the tenant boundary mandatory.
    op.execute(
        "UPDATE outbox_messages "
        "SET project_id = (SELECT project_id FROM jobs WHERE jobs.id = outbox_messages.aggregate_id)"
    )

    with op.batch_alter_table("outbox_messages") as batch_op:
        batch_op.alter_column("project_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_outbox_messages_project_id_projects", "projects", ["project_id"], ["id"]
        )
        batch_op.create_index("ix_outbox_messages_project_id", ["project_id"])


def downgrade() -> None:
    with op.batch_alter_table("outbox_messages") as batch_op:
        batch_op.drop_index("ix_outbox_messages_project_id")
        batch_op.drop_constraint(
            "fk_outbox_messages_project_id_projects", type_="foreignkey"
        )
        batch_op.drop_column("project_id")
