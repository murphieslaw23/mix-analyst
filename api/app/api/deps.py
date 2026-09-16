"""API-key guard for mutation endpoints.

Reads stay open (radio metadata + PWA use-case). When `API_KEYS` is
configured, every write path requires a valid `X-API-Key` header.
When empty (default single-user mode), all requests pass through.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from ..config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def key_is_valid(provided: str | None) -> bool:
    """Pure check, unit-testable without HTTP machinery."""
    configured = settings.api_keys
    if not configured:
        return True
    return bool(provided) and provided in configured


async def require_api_key(provided: str | None = Depends(api_key_header)) -> None:
    if key_is_valid(provided):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid X-API-Key header required for this operation",
    )
