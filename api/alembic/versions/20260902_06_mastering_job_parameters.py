"""Persist durable mastering command settings on jobs.

Revision ID: 20260902_06_mastering_job_parameters
Revises: 20260902_05_job_events
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_06_mastering_job_parameters"
down_revision: Union[str, Sequence[str], None] = "20260902_05_job_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("parameters", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("parameters")
