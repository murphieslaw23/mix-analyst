"""Executable deployment-contract regressions for the final core repair wave."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SAFE_TEST_SECRET = "test-only-compose-secret-with-at-least-32-bytes"


def _compose_config(*, auth_secret: str | None):
    environment = os.environ.copy()
    environment.pop("AUTH_JWT_SECRET", None)
    if auth_secret is not None:
        environment["AUTH_JWT_SECRET"] = auth_secret
    return subprocess.run(
        ["docker", "compose", "-f", "docker-compose.yml", "config", "--format", "json"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _has_storage_volume(service: dict) -> bool:
    return any(
        volume.get("type") == "volume"
        and volume.get("source") == "storage_data"
        and volume.get("target") == "/storage"
        for volume in service.get("volumes", [])
    )


def test_shipped_compose_requires_auth_secret_and_mounts_one_storage_root():
    """Removing auth interpolation or either shared mount makes this contract fail."""
    missing_secret = _compose_config(auth_secret=None)
    assert missing_secret.returncode != 0
    assert "AUTH_JWT_SECRET" in missing_secret.stderr

    rendered = _compose_config(auth_secret=SAFE_TEST_SECRET)
    assert rendered.returncode == 0, rendered.stderr
    config = json.loads(rendered.stdout)
    api = config["services"]["api"]
    worker = config["services"]["worker"]
    outbox = config["services"]["outbox-dispatcher"]
    beat = config["services"]["celery-beat"]

    assert api["environment"]["AUTH_JWT_SECRET"] == SAFE_TEST_SECRET
    assert api["environment"]["APP_ENV"] == "production"
    assert api["environment"]["STORAGE_DIR"] == "/storage"
    assert worker["environment"]["STORAGE_DIR"] == "/storage"
    assert outbox["environment"]["STORAGE_DIR"] == "/storage"
    assert beat["environment"]["STORAGE_DIR"] == "/storage"
    assert _has_storage_volume(api)
    assert _has_storage_volume(worker)
    assert _has_storage_volume(outbox)
    assert _has_storage_volume(beat)
    assert "beat" in " ".join(beat["command"])


def test_broker_queue_storage_uses_a_non_evicting_policy():
    """An eviction policy must never discard accepted durable queue entries."""
    rendered = _compose_config(auth_secret=SAFE_TEST_SECRET)
    assert rendered.returncode == 0, rendered.stderr
    config = json.loads(rendered.stdout)
    command = config["services"]["redis"]["command"]
    command_text = " ".join(command) if isinstance(command, list) else command
    assert "--maxmemory-policy noeviction" in command_text


def test_worker_resolves_storage_dir_through_the_shared_settings_alias():
    """The worker must consume STORAGE_DIR just like the upload API does."""
    environment = os.environ | {
        "PYTHONPATH": str(REPOSITORY_ROOT),
        "STORAGE_DIR": "/storage/from-compose",
    }
    result = subprocess.run(
        [sys.executable, "-c", "import worker.tasks; print(worker.tasks.STORAGE_ROOT)"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "/storage/from-compose"
