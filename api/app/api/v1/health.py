import shutil
import tempfile
from pathlib import Path

import redis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...config import settings
from ...db.session import get_db

router = APIRouter()


def ping_redis() -> bool:
    """Perform a real broker round-trip for readiness, not a configuration check."""
    client = redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        return bool(client.ping())
    except Exception:  # noqa: BLE001 - readiness must degrade for any broker failure.
        return False
    finally:
        client.close()


def storage_is_ready() -> bool:
    """Verify writable persistent storage has room for the configured admission."""
    test_path: Path | None = None
    try:
        storage_path = Path(settings.storage_root)
        storage_path.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(storage_path).free < settings.min_storage_free_bytes:
            return False
        # A fixed sentinel races concurrent readiness probes and can cause one
        # healthy request to unlink another's file. The OS allocates a unique
        # name, and the finally block makes cleanup deterministic on failures.
        descriptor, raw_path = tempfile.mkstemp(
            prefix=".healthcheck-", dir=storage_path
        )
        test_path = Path(raw_path)
        # A successful open alone is not enough for a persistence volume.
        # Flush the tiny sentinel before declaring the path writable.
        with open(descriptor, "wb", closefd=True) as handle:
            handle.write(b"ok")
            handle.flush()
        return test_path.is_file()
    except Exception:  # noqa: BLE001 - readiness must degrade for filesystem failures.
        return False
    finally:
        if test_path is not None:
            try:
                test_path.unlink(missing_ok=True)
            except OSError:
                pass


@router.get("/live")
def health_live():
    """Liveness intentionally proves only that this API process can serve requests."""
    return {"status": "ok", "checks": {"process": "ok"}}


@router.get("/ready")
def health_ready(db: Session = Depends(get_db)):
    """Readiness probe: validates database connection and storage availability."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001 - readiness must degrade for database failures.
        db_ok = False

    storage_ok = storage_is_ready()
    redis_ok = ping_redis()

    all_ready = db_ok and storage_ok and redis_ok
    status_str = "ok" if all_ready else "degraded"

    body = {
        "status": status_str,
        "checks": {
            "database": "ok" if db_ok else "error",
            "storage": "ok" if storage_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    }
    return JSONResponse(status_code=200 if all_ready else 503, content=body)
