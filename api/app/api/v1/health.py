from pathlib import Path
from typing import Annotated

import redis
from fastapi import APIRouter, Depends
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...config import settings
from ...db.session import get_db

router = APIRouter()


@router.get("/live")
def health_live():
    """Liveness probe."""
    return {"status": "ok"}


def _check_redis() -> bool:
    """Ping the broker/result backend instead of assuming it is up."""
    try:
        client = redis.from_url(
            settings.redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        return client.ping() is True
    except (RedisError, OSError):
        return False


@router.get("/ready")
def health_ready(db: Annotated[Session, Depends(get_db)]):
    """Readiness probe: validates database connection and storage availability."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except SQLAlchemyError:
        db_ok = False

    storage_ok = False
    try:
        storage_path = Path(settings.storage_root)
        storage_path.mkdir(parents=True, exist_ok=True)
        test_file = storage_path / ".healthcheck"
        test_file.touch()
        test_file.unlink()
        storage_ok = True
    except OSError:
        storage_ok = False

    all_ready = db_ok and storage_ok
    redis_ok = _check_redis()
    status_str = "ok" if (all_ready and redis_ok) else "degraded"

    return {
        "status": status_str,
        "checks": {
            "database": "ok" if db_ok else "error",
            "storage": "ok" if storage_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    }
