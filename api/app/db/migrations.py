"""Apply Alembic migrations to head.

Migrations (api/alembic/versions) are the authority for the schema;
the application never calls Base.metadata.create_all() at runtime.
"""

from alembic import command
from alembic.config import Config


def upgrade_to_head(alembic_ini: str = "api/alembic.ini") -> None:
    """Upgrade the configured database to the single Alembic head."""
    cfg = Config(alembic_ini)
    command.upgrade(cfg, "head")
