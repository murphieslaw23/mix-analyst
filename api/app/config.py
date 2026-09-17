import json
import os
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Mix Analyst"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # CORS
    allowed_origins: Annotated[set[str], NoDecode] = {
        "http://localhost:3000",
        "http://localhost:5173",
    }

    # Database
    database_url: str = "postgresql://postgres:postgres@db:5432/mixanalyst"

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    # Storage (STORAGE_ROOT canonical for compose; STORAGE_DIR accepted
    # as a legacy alias from the deployment contract).
    storage_root: str = "/data/storage"
    max_upload_size_bytes: int = 4 * 1024 * 1024 * 1024  # 4 GB max per mix
    default_chunk_size_bytes: int = 5 * 1024 * 1024  # 5 MB per chunk

    # Upload hygiene
    upload_expiry_hours: int = 24  # stale PENDING sessions older than this are purged

    # Auth: comma-separated API keys guarding mutation endpoints.
    # Empty (default) = single-user open mode, reads always stay open.
    api_keys: Annotated[set[str], NoDecode] = set()

    # Rate limiting for write methods (POST/PUT/DELETE). 0 disables.
    rate_limit_per_minute: int = 60

    @field_validator("storage_root", mode="before")
    @classmethod
    def apply_storage_dir_alias(cls, value: object) -> object:
        # An explicitly configured STORAGE_ROOT (environment or .env)
        # always wins; STORAGE_DIR only fills the gap.
        if "STORAGE_ROOT" not in os.environ:
            legacy = os.environ.get("STORAGE_DIR")
            if legacy:
                return legacy
        return value

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.startswith("["):
            return set(json.loads(value))
        return {origin.strip() for origin in value.split(",") if origin.strip()}

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return {key.strip() for key in value.split(",") if key.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
