from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, inspect, pool, text

import api.app.models  # noqa: F401 - imports the canonical model metadata
from api.app.config import settings
from api.app.db.session import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# These tables together identify the schema that existed immediately before
# Alembic was introduced. A partial or unrelated database must not be stamped.
LEGACY_BASELINE_TABLES = {
    "media_assets",
    "upload_sessions",
    "mixes",
    "mastering_presets",
    "jobs",
    "analysis_results",
    "track_segments",
    "transition_events",
    "mastering_jobs",
    "broadcast_syncs",
    "stem_jobs",
    "job_attempts",
    "stage_runs",
    "track_matches",
}
BASELINE_REVISION = "20260902_01"


def _adopt_verified_legacy_baseline(connection) -> bool:
    """Stamp only a complete pre-Alembic schema so later migrations can run."""
    tables = set(inspect(connection).get_table_names())
    if "alembic_version" in tables or not LEGACY_BASELINE_TABLES.issubset(tables):
        # SQLAlchemy inspection may autobegin a read transaction. Close it so
        # Alembic can own the migration transaction below.
        if connection.in_transaction():
            connection.rollback()
        return False

    # Inspection can autobegin a transaction in SQLAlchemy 2. End that read
    # transaction before stamping, then commit the adoption independently so
    # Alembic's normal migration transaction starts from a stable revision.
    if connection.in_transaction():
        connection.rollback()
    connection.execute(
        text(
            "CREATE TABLE alembic_version ("
            "version_num VARCHAR(32) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        )
    )
    connection.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
        {"revision": BASELINE_REVISION},
    )
    connection.commit()
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _adopt_verified_legacy_baseline(connection)
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
