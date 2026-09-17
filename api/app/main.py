from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.api.rate_limit import RateLimitMiddleware
from api.app.api.v1 import (
    batches,
    broadcast,
    compositor,
    export,
    health,
    jobs,
    mastering,
    metrics,
    mixes,
    notifications,
    sidechain,
    stems,
    uploads,
)
from api.app.config import settings
from api.app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)

app.include_router(
    health.router, prefix=f"{settings.api_v1_prefix}/health", tags=["health"]
)
app.include_router(
    uploads.router, prefix=f"{settings.api_v1_prefix}/uploads", tags=["uploads"]
)
app.include_router(batches.router, prefix=settings.api_v1_prefix, tags=["batches"])
app.include_router(jobs.router, prefix=settings.api_v1_prefix, tags=["jobs"])
app.include_router(metrics.router, prefix=settings.api_v1_prefix, tags=["metrics"])
app.include_router(
    notifications.router, prefix=settings.api_v1_prefix, tags=["notifications"]
)
app.include_router(
    mixes.router, prefix=f"{settings.api_v1_prefix}/mixes", tags=["mixes"]
)
app.include_router(
    export.router, prefix=f"{settings.api_v1_prefix}/mixes", tags=["export"]
)
app.include_router(mastering.router, prefix=settings.api_v1_prefix, tags=["mastering"])
app.include_router(broadcast.router, prefix=settings.api_v1_prefix, tags=["broadcast"])
app.include_router(stems.router, prefix=settings.api_v1_prefix, tags=["stems"])
app.include_router(
    compositor.router, prefix=settings.api_v1_prefix, tags=["compositor"]
)
app.include_router(sidechain.router, prefix=settings.api_v1_prefix, tags=["sidechain"])
