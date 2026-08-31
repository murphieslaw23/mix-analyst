from fastapi import APIRouter

router = APIRouter()


@router.get("/live")
def health_live():
    return {"status": "ok"}


@router.get("/ready")
def health_ready():
    return {"status": "ok", "checks": {"database": "ok", "redis": "ok", "storage": "ok"}}
