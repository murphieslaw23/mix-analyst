from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import api.app.models  # noqa: F401 - registers the complete SQLAlchemy metadata
from api.app.api.v1 import (
    batches,
    health,
    jobs,
    mastering,
    metrics,
    mixes,
    notifications,
    push,
    uploads,
)
from api.app.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_deployment_auth()
    yield


app = FastAPI(
    title=settings.app_name,
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    health.router, prefix=f"{settings.api_v1_prefix}/health", tags=["health"]
)
app.include_router(metrics.router, prefix=settings.api_v1_prefix, tags=["operations"])
# Upload sessions use the legacy root-level `/{upload_id}` path. Register the
# named job routes first so an upload parameter route cannot capture `/jobs`.
app.include_router(jobs.router, prefix=settings.api_v1_prefix, tags=["jobs"])
app.include_router(
    notifications.router, prefix=settings.api_v1_prefix, tags=["notifications"]
)
app.include_router(push.router, prefix=settings.api_v1_prefix, tags=["push"])
app.include_router(uploads.router, prefix=settings.api_v1_prefix, tags=["uploads"])
app.include_router(
    mixes.router, prefix=f"{settings.api_v1_prefix}/mixes", tags=["mixes"]
)
app.include_router(mastering.router, prefix=settings.api_v1_prefix, tags=["mastering"])
app.include_router(batches.router, prefix=settings.api_v1_prefix, tags=["batches"])
