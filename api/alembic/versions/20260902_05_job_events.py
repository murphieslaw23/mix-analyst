"""Persist ordered job events for replayable progress streams.

Revision ID: 20260902_05_job_events
Revises: 20260902_04_outbox_project_scope
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_05_job_events"
down_revision: str | Sequence[str] | None = "20260902_04_outbox_project_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "event_sequence", sa.Integer(), nullable=False, server_default="0"
            )
        )

    op.create_table(
        "job_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "sequence", name="uq_job_events_job_id_sequence"),
    )
    op.create_index("ix_job_events_project_id", "job_events", ["project_id"])
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])
    op.create_index(
        "ix_job_events_project_job_sequence",
        "job_events",
        ["project_id", "job_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_events_project_job_sequence", table_name="job_events")
    op.drop_index("ix_job_events_job_id", table_name="job_events")
    op.drop_index("ix_job_events_project_id", table_name="job_events")
    op.drop_table("job_events")
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("event_sequence")
