"""Regression tests for settings parsing."""

import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_comma_separated_allowed_origins_are_accepted():
    """The documented .env CORS format must allow application startup."""
    env = os.environ | {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "ALLOWED_ORIGINS": "http://localhost:3000,http://localhost:5173",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from api.app.config import settings; "
            "assert settings.allowed_origins == {'http://localhost:3000', 'http://localhost:5173'}",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
