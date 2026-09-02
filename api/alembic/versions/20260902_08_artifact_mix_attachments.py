"""Allow one immutable object to be attached to multiple project mixes.

Revision ID: 20260902_08_artifact_mix_attachments
Revises: 20260902_08_artifacts
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260902_08_artifact_mix_attachments"
down_revision: Union[str, Sequence[str], None] = "20260902_08_artifacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("artifacts") as batch_op:
        batch_op.drop_constraint("uq_artifacts_project_key", type_="unique")
        batch_op.create_unique_constraint("uq_artifacts_project_mix_key", ["project_id", "mix_id", "key"])


def downgrade() -> None:
    with op.batch_alter_table("artifacts") as batch_op:
        batch_op.drop_constraint("uq_artifacts_project_mix_key", type_="unique")
        batch_op.create_unique_constraint("uq_artifacts_project_key", ["project_id", "key"])
