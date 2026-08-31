from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import health, uploads, mixes, jobs
from .config import settings
from .db.session import init_db
from .services.storage import StorageService


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = StorageService(settings.storage_root)
    storage.init_directories()

    try:
        init_db()
    except Exception as e:
        print(f"Warning: Database initialization pending: {e}")

    yield


app = FastAPI(
    title="Mix Analyst API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["Uploads"])
app.include_router(mixes.router, prefix="/api/v1/mixes", tags=["Mixes"])
app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])


@app.get("/health/live", tags=["Health"])
def health_live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["Health"])
def health_ready():
    return {"status": "ok"}
