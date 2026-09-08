import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_app_uses_declared_settings_contract():
    from api.app.main import app

    assert app.title == "Mix Analyst"
    assert app.openapi_url == "/api/v1/openapi.json"


def test_compose_storage_alias_is_applied(monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", "/storage")

    from api.app.config import Settings

    assert Settings().storage_root == "/storage"


def test_baseline_preserves_server_generated_timestamps(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'baseline.db'}"
    environment = os.environ | {"DATABASE_URL": database_url}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "api/alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    from api.app.models.broadcast import BroadcastSync
    from api.app.models.mastering import MasteringJob, MasteringPreset
    from api.app.models.stems import StemJob

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        for table_name, model in (
            ("mastering_presets", MasteringPreset),
            ("mastering_jobs", MasteringJob),
            ("broadcast_syncs", BroadcastSync),
            ("stem_jobs", StemJob),
        ):
            created_at = next(
                column
                for column in inspector.get_columns(table_name)
                if column["name"] == "created_at"
            )
            assert created_at["default"] is not None
            assert created_at["nullable"] is model.__table__.c.created_at.nullable
    finally:
        engine.dispose()
