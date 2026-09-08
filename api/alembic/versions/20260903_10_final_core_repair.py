"""Fence job attempts and recover final upload promotion.

Revision ID: 20260903_10_final_core_repair
Revises: 20260902_09_batches
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_10_final_core_repair"
down_revision: str | Sequence[str] | None = "20260902_09_batches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_attempts") as batch_op:
        batch_op.add_column(
            sa.Column("claim_token", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index("ix_job_attempts_claim_token", ["claim_token"])
        batch_op.create_index("ix_job_attempts_lease_expires_at", ["lease_expires_at"])

    with op.batch_alter_table("job_events") as batch_op:
        batch_op.add_column(
            sa.Column(
                "attempt_number", sa.Integer(), nullable=False, server_default="1"
            )
        )
        batch_op.alter_column("attempt_number", server_default=None)

    with op.batch_alter_table("upload_sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "promotion_state",
                sa.String(length=32),
                nullable=False,
                server_default="NONE",
            )
        )
        batch_op.add_column(
            sa.Column("final_key", sa.String(length=512), nullable=True)
        )
        batch_op.add_column(
            sa.Column("media_asset_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(sa.Column("mix_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_upload_sessions_media_asset_id_media_assets",
            "media_assets",
            ["media_asset_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_upload_sessions_mix_id_mixes", "mixes", ["mix_id"], ["id"]
        )
        batch_op.alter_column("promotion_state", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("upload_sessions") as batch_op:
        batch_op.drop_constraint("fk_upload_sessions_mix_id_mixes", type_="foreignkey")
        batch_op.drop_constraint(
            "fk_upload_sessions_media_asset_id_media_assets", type_="foreignkey"
        )
        batch_op.drop_column("mix_id")
        batch_op.drop_column("media_asset_id")
        batch_op.drop_column("final_key")
        batch_op.drop_column("promotion_state")

    with op.batch_alter_table("job_events") as batch_op:
        batch_op.drop_column("attempt_number")

    with op.batch_alter_table("job_attempts") as batch_op:
        batch_op.drop_index("ix_job_attempts_lease_expires_at")
        batch_op.drop_index("ix_job_attempts_claim_token")
        batch_op.drop_column("lease_expires_at")
        batch_op.drop_column("last_heartbeat_at")
        batch_op.drop_column("claim_token")
