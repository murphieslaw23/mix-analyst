import json
from functools import lru_cache
from typing import Annotated, Set

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    app_name: str = "Mix Analyst"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # CORS
    web_origin: str = "http://localhost:3000"
    allowed_origins: Annotated[Set[str], NoDecode] = {"http://localhost:3000", "http://localhost:5173"}

    # Database
    database_url: str = "postgresql://postgres:postgres@db:5432/mixanalyst"

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    # Storage
    storage_root: str = "/data/storage"
    max_upload_size_bytes: int = 4 * 1024 * 1024 * 1024  # 4 GB max per mix
    default_chunk_size_bytes: int = 5 * 1024 * 1024      # 5 MB per chunk

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.startswith("["):
            return set(json.loads(value))
        return {origin.strip() for origin in value.split(",") if origin.strip()}

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
