from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEVELOPMENT_JWT_SECRET = "development-only-secret-change-me-32"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = Field("Mix Analyst", validation_alias="APP_NAME")
    debug: bool = Field(False, validation_alias="DEBUG")
    api_v1_prefix: str = Field("/api/v1", validation_alias="API_V1_PREFIX")

    # Authentication.  The development fallback keeps local fixtures simple;
    # deployments opt into the fail-closed check through APP_ENV=production.
    # Compose always supplies a required non-default value.
    app_env: str = Field("development", validation_alias="APP_ENV")
    auth_jwt_secret: str = Field(
        DEFAULT_DEVELOPMENT_JWT_SECRET, validation_alias="AUTH_JWT_SECRET"
    )
    auth_jwt_algorithm: str = Field("HS256", validation_alias="AUTH_JWT_ALGORITHM")

    # Web Push. Subscription secrets are encrypted before persistence. A
    # dedicated key is preferred; the deployment JWT secret is the fallback
    # root key so development fixtures do not require a second secret.
    push_encryption_key: str | None = Field(
        None, validation_alias="PUSH_ENCRYPTION_KEY"
    )
    vapid_public_key: str | None = Field(None, validation_alias="VAPID_PUBLIC_KEY")
    vapid_private_key: str | None = Field(None, validation_alias="VAPID_PRIVATE_KEY")
    vapid_contact: str | None = Field(None, validation_alias="VAPID_CONTACT")

    # CORS
    web_origin: str = Field("http://localhost:3000", validation_alias="WEB_ORIGIN")
    allowed_origins: set[str] = Field(
        {"http://localhost:3000", "http://localhost:5173"},
        validation_alias="CORS_ORIGINS",
    )

    # Database
    database_url: str = Field(
        "postgresql://postgres:postgres@db:5432/mixanalyst",
        validation_alias="DATABASE_URL",
    )

    # Redis / Celery
    redis_url: str = Field("redis://redis:6379/0", validation_alias="REDIS_URL")
    celery_broker_url: str = Field(
        "redis://redis:6379/0", validation_alias="CELERY_BROKER_URL"
    )
    celery_result_backend: str = Field(
        "redis://redis:6379/0", validation_alias="CELERY_RESULT_BACKEND"
    )

    # Storage
    storage_root: str = Field("/data/storage", validation_alias="STORAGE_DIR")
    max_upload_size_bytes: int = Field(
        4 * 1024 * 1024 * 1024, gt=0, validation_alias="MAX_UPLOAD_SIZE_BYTES"
    )
    max_chunk_size_bytes: int = Field(
        8 * 1024 * 1024, gt=0, validation_alias="MAX_CHUNK_SIZE_BYTES"
    )
    default_chunk_size_bytes: int = Field(
        5 * 1024 * 1024, gt=0, validation_alias="DEFAULT_CHUNK_SIZE_BYTES"
    )
    upload_session_ttl_seconds: int = Field(
        24 * 60 * 60, gt=0, validation_alias="UPLOAD_SESSION_TTL_SECONDS"
    )
    min_storage_free_bytes: int = Field(
        5 * 1024 * 1024 * 1024, gt=0, validation_alias="MIN_STORAGE_FREE_BYTES"
    )
    job_attempt_lease_seconds: int = Field(
        5 * 60, gt=0, validation_alias="JOB_ATTEMPT_LEASE_SECONDS"
    )

    def validate_deployment_auth(self) -> None:
        """Reject a known development credential in a deployed API process.

        Unit/integration fixtures intentionally run with the development
        setting.  Production and staging must provide an independently held,
        sufficiently long secret before the API starts accepting requests.
        """
        if self.app_env.strip().lower() not in {"production", "prod", "staging"}:
            return
        if (
            self.auth_jwt_secret == DEFAULT_DEVELOPMENT_JWT_SECRET
            or len(self.auth_jwt_secret) < 32
        ):
            raise RuntimeError(
                "AUTH_JWT_SECRET must be a non-default secret of at least 32 characters"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
