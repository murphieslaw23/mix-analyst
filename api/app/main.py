from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.app.config import settings
from api.app.api.v1 import health, uploads, jobs, mixes, export, mastering, broadcast, stems

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.API_V1_STR, tags=["health"])
app.include_router(uploads.router, prefix=settings.API_V1_STR, tags=["uploads"])
app.include_router(jobs.router, prefix=settings.API_V1_STR, tags=["jobs"])
app.include_router(mixes.router, prefix=f"{settings.API_V1_STR}/mixes", tags=["mixes"])
app.include_router(export.router, prefix=f"{settings.API_V1_STR}/mixes", tags=["export"])
app.include_router(mastering.router, prefix=settings.API_V1_STR, tags=["mastering"])
app.include_router(broadcast.router, prefix=settings.API_V1_STR, tags=["broadcast"])
app.include_router(stems.router, prefix=settings.API_V1_STR, tags=["stems"])
