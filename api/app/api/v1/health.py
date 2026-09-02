import shutil
from pathlib import Path

import redis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from ...db.session import get_db
from ...config import settings

router = APIRouter()


def ping_redis() -> bool:
    """Perform a real broker round-trip for readiness, not a configuration check."""
    client = redis.from_url(
        settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
    )
    try:
        return bool(client.ping())
    except Exception:
        return False
    finally:
        client.close()


def storage_is_ready() -> bool:
    """Verify writable persistent storage has room for the configured admission."""
    try:
        storage_path = Path(settings.storage_root)
        storage_path.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(storage_path).free < settings.min_storage_free_bytes:
            return False
        test_file = storage_path / ".healthcheck"
        test_file.touch()
        test_file.unlink()
        return True
    except Exception:
        return False


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
    except Exception:
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
