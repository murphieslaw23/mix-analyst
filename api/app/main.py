from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.app.config import settings
from api.app.api.v1 import health, uploads, jobs, mixes, mastering
import api.app.models  # noqa: F401 - registers the complete SQLAlchemy metadata

app = FastAPI(
    title=settings.app_name,
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_v1_prefix, tags=["health"])
app.include_router(uploads.router, prefix=settings.api_v1_prefix, tags=["uploads"])
app.include_router(jobs.router, prefix=settings.api_v1_prefix, tags=["jobs"])
app.include_router(mixes.router, prefix=f"{settings.api_v1_prefix}/mixes", tags=["mixes"])
app.include_router(mastering.router, prefix=settings.api_v1_prefix, tags=["mastering"])
