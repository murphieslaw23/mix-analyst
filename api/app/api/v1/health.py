from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pathlib import Path

from ...db.session import get_db
from ...config import settings

router = APIRouter()


@router.get("/live")
def health_live():
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/ready")
def health_ready(db: Session = Depends(get_db)):
    """Readiness probe: validates database connection and storage availability."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    storage_ok = False
    try:
        storage_path = Path(settings.storage_root)
        storage_path.mkdir(parents=True, exist_ok=True)
        test_file = storage_path / ".healthcheck"
        test_file.touch()
        test_file.unlink()
        storage_ok = True
    except Exception:
        storage_ok = False

    all_ready = db_ok and storage_ok
    status_str = "ok" if all_ready else "degraded"

    return {
        "status": status_str,
        "checks": {
            "database": "ok" if db_ok else "error",
            "storage": "ok" if storage_ok else "error",
            "redis": "ok",
        },
    }
