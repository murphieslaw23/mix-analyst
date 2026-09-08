"""Regression coverage for adopting persistent databases created before Alembic."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_complete_pre_alembic_schema_is_stamped_then_upgraded(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'legacy-pre-alembic.db'}"
    environment = os.environ | {
        "DATABASE_URL": database_url,
        "PYTHONPATH": str(REPOSITORY_ROOT),
    }
    command = [sys.executable, "-m", "alembic", "-c", "api/alembic.ini", "upgrade"]

    baseline = subprocess.run(
        [*command, "20260902_01"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert baseline.returncode == 0, baseline.stderr

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))
    assert "alembic_version" not in inspect(engine).get_table_names()

    upgraded = subprocess.run(
        [*command, "head"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert upgraded.returncode == 0, upgraded.stderr

    inspector = inspect(engine)
    assert {
        "alembic_version",
        "users",
        "projects",
        "artifacts",
        "job_events",
        "notifications",
        "push_subscriptions",
        "push_deliveries",
    }.issubset(set(inspector.get_table_names()))
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert revision == "20260908_13_push"
