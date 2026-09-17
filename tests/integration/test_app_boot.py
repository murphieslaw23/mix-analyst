"""Boot contract: declared settings, storage alias, migration authority."""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_app_uses_declared_settings_contract():
    from api.app.main import app

    assert app.title == "Mix Analyst"
    assert app.openapi_url == "/api/v1/openapi.json"


def test_compose_storage_alias_is_applied():
    """STORAGE_DIR (and the compose STORAGE_ROOT) must both configure storage."""
    child_code = (
        "import os; from api.app.config import Settings; "
        "assert Settings().storage_root == os.environ['EXPECTED_STORAGE_ROOT'], "
        "Settings().storage_root"
    )
    for var, expected in (("STORAGE_DIR", "/storage"), ("STORAGE_ROOT", "/data-vol")):
        env = {
            key: val
            for key, val in os.environ.items()
            if key not in ("STORAGE_DIR", "STORAGE_ROOT")
        } | {
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            var: expected,
            "EXPECTED_STORAGE_ROOT": expected,
        }
        result = subprocess.run(
            [sys.executable, "-c", child_code],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_alembic_reports_exactly_one_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(PROJECT_ROOT / "api" / "alembic.ini"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert len(heads) == 1


def test_revision_ids_fit_alembic_version_column():
    """alembic_version.version_num is varchar(32): longer ids roll back DDL."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(PROJECT_ROOT / "api" / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    revisions = list(script.walk_revisions())
    assert revisions
    for rev in revisions:
        assert len(rev.revision) <= 32, rev.revision
