"""Persist encrypted Push subscriptions and delivery attempts.

Revision ID: 20260908_13_push
Revises: 20260905_12_notifications
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_13_push"
down_revision: str | Sequence[str] | None = "20260905_12_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("endpoint_hash", sa.String(length=64), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint_hash", name="uq_push_subscriptions_endpoint_hash"),
    )
    op.create_index("ix_push_subscriptions_project_id", "push_subscriptions", ["project_id"])
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
    op.create_index("ix_push_subscriptions_active", "push_subscriptions", ["active"])

    op.create_table(
        "push_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("notification_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["push_subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id",
            "subscription_id",
            name="uq_push_deliveries_notification_subscription",
        ),
    )
    op.create_index("ix_push_deliveries_notification_id", "push_deliveries", ["notification_id"])
    op.create_index("ix_push_deliveries_subscription_id", "push_deliveries", ["subscription_id"])
    op.create_index("ix_push_deliveries_status", "push_deliveries", ["status"])
    op.create_index("ix_push_deliveries_next_attempt_at", "push_deliveries", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_push_deliveries_next_attempt_at", table_name="push_deliveries")
    op.drop_index("ix_push_deliveries_status", table_name="push_deliveries")
    op.drop_index("ix_push_deliveries_subscription_id", table_name="push_deliveries")
    op.drop_index("ix_push_deliveries_notification_id", table_name="push_deliveries")
    op.drop_table("push_deliveries")
    op.drop_index("ix_push_subscriptions_active", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_project_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
