"""Persist batch parents and link their durable child jobs.

Revision ID: 20260902_09_batches
Revises: 20260902_08_artifact_mix_attachments
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_09_batches"
down_revision: Union[str, Sequence[str], None] = "20260902_08_artifact_mix_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


batch_status = sa.Enum(
    "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "PARTIAL_FAILED", "CANCELLED", name="batchstatus"
)


def upgrade() -> None:
    op.create_table(
        "batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("preset", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("max_parallelism", sa.Integer(), nullable=False),
        sa.Column("status", batch_status, nullable=False, server_default="QUEUED"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancelled_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_batches_project_id", "batches", ["project_id"])
    op.create_index("ix_batches_status", "batches", ["status"])
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("batch_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key("fk_jobs_batch_id_batches", "batches", ["batch_id"], ["id"])
        batch_op.create_index("ix_jobs_batch_id", ["batch_id"])


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_index("ix_jobs_batch_id")
        batch_op.drop_constraint("fk_jobs_batch_id_batches", type_="foreignkey")
        batch_op.drop_column("batch_id")
    op.drop_index("ix_batches_status", table_name="batches")
    op.drop_index("ix_batches_project_id", table_name="batches")
    op.drop_table("batches")
