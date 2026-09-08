"""Add server-owned keys and authoritative offsets to upload sessions.

Revision ID: 20260902_03_upload_sessions
Revises: 20260902_03
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_03_upload_sessions"
down_revision: str | Sequence[str] | None = "20260902_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("upload_sessions") as batch_op:
        batch_op.add_column(
            sa.Column("offset", sa.BigInteger(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "content_type",
                sa.String(length=100),
                nullable=False,
                server_default="application/octet-stream",
            )
        )
        batch_op.add_column(
            sa.Column("quarantine_key", sa.String(length=512), nullable=True)
        )
        batch_op.add_column(
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
        )

    # Legacy rows may contain absolute temp_path values. Deliberately do not
    # copy them into the new key field: they expire instead of becoming path
    # capabilities in the new lifecycle.
    op.execute("UPDATE upload_sessions SET offset = bytes_received")
    op.execute("UPDATE upload_sessions SET quarantine_key = 'legacy/' || id")
    op.execute("UPDATE upload_sessions SET expires_at = created_at")

    with op.batch_alter_table("upload_sessions") as batch_op:
        batch_op.alter_column("offset", server_default=None)
        batch_op.alter_column("content_type", server_default=None)
        batch_op.alter_column("quarantine_key", nullable=False)
        batch_op.alter_column("expires_at", nullable=False)
        batch_op.create_index("ix_upload_sessions_expires_at", ["expires_at"])


def downgrade() -> None:
    with op.batch_alter_table("upload_sessions") as batch_op:
        batch_op.drop_index("ix_upload_sessions_expires_at")
        batch_op.drop_column("expires_at")
        batch_op.drop_column("quarantine_key")
        batch_op.drop_column("content_type")
        batch_op.drop_column("offset")
