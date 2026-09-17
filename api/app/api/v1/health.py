from pathlib import Path
from typing import Annotated

import redis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
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
    """Readiness probe: database, storage and broker must all answer.

    Returns 503 while any dependency is down so orchestrators stop
    routing traffic instead of serving a degraded API as healthy.
    """
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

    redis_ok = _check_redis()
    all_ready = db_ok and storage_ok and redis_ok

    body = {
        "status": "ok" if all_ready else "degraded",
        "checks": {
            "database": "ok" if db_ok else "error",
            "storage": "ok" if storage_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    }
    if all_ready:
        return body
    return JSONResponse(status_code=503, content=body)
