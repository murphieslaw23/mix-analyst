"""Regression tests for the deployable Compose contract."""

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_primary_compose_file_validates():
    """The production stack must be accepted by Docker Compose before deployment."""
    result = subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
