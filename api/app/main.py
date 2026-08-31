from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import health
from .config import settings

app = FastAPI(title="Mix Analyst API", version="0.1.0")

# CORS for local dev (Vercel web frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1/health")


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    # Placeholder: will check DB, Redis, storage in Phase 1+
    return {"status": "ok", "checks": {"database": "ok", "redis": "ok", "storage": "ok"}}
