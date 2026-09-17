"""API-key guard for mutation endpoints.

Reads stay open (radio metadata + PWA use-case). When `API_KEYS` is
configured, every write path requires a valid `X-API-Key` header.
When empty (default single-user mode), all requests pass through.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from ..config import settings
from ..db.session import get_db
from ..schemas.auth import CurrentPrincipal
from ..services.auth import resolve_principal

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


async def get_current_principal(
    request: Request, db: Annotated[Session, Depends(get_db)]
) -> CurrentPrincipal:
    """Authenticate the caller and fix their project scope for this request."""
    return resolve_principal(request, db)
