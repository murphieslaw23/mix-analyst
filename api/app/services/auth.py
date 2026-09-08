from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models.identity import Project, User
from ..schemas.auth import CurrentPrincipal

ARTIFACT_TICKET_AUDIENCE = "mix-analyst-artifact"
ARTIFACT_TICKET_MIN_TTL_SECONDS = 15 * 60
ARTIFACT_TICKET_MAX_TTL_SECONDS = 12 * 60 * 60


def decode_principal_token(token: str) -> CurrentPrincipal:
    """Validate a signed bearer token and extract its selected project."""
    try:
        claims = jwt.decode(
            token,
            settings.auth_jwt_secret,
            algorithms=[settings.auth_jwt_algorithm],
            options={"require": ["sub", "project_id"]},
        )
        return CurrentPrincipal(user_id=claims["sub"], project_id=claims["project_id"])
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        raise ValueError("Invalid bearer token") from None


def require_persisted_project_membership(
    db: Session, principal: CurrentPrincipal
) -> CurrentPrincipal:
    """Ensure a correctly signed claim names a project actually owned by its user."""
    membership = db.scalar(
        select(Project.id)
        .join(User, User.id == Project.owner_id)
        .where(
            Project.id == principal.project_id,
            Project.owner_id == principal.user_id,
            User.id == principal.user_id,
        )
    )
    if membership is None:
        raise ValueError("Bearer token project membership is invalid")
    return principal


def artifact_ticket_ttl(duration_seconds: float | None) -> int:
    """Cover a complete long-form listen while keeping the capability bounded."""
    duration = max(0, int(duration_seconds or 0))
    return min(
        ARTIFACT_TICKET_MAX_TTL_SECONDS,
        max(ARTIFACT_TICKET_MIN_TTL_SECONDS, duration + 15 * 60),
    )


def issue_artifact_ticket(
    principal: CurrentPrincipal,
    mix_id: str,
    artifact_id: str,
    *,
    ttl_seconds: int = ARTIFACT_TICKET_MIN_TTL_SECONDS,
) -> str:
    """Mint a narrowly scoped capability for native media Range requests."""
    ttl = min(ARTIFACT_TICKET_MAX_TTL_SECONDS, max(60, int(ttl_seconds)))
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": principal.user_id,
            "project_id": principal.project_id,
            "mix_id": mix_id,
            "artifact_id": artifact_id,
            "scope": "artifact:read",
            "aud": ARTIFACT_TICKET_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(seconds=ttl),
        },
        settings.auth_jwt_secret,
        algorithm=settings.auth_jwt_algorithm,
    )


def decode_artifact_ticket(
    token: str, mix_id: str, artifact_id: str
) -> CurrentPrincipal:
    """Validate an artifact ticket and bind it to the exact requested object."""
    try:
        claims = jwt.decode(
            token,
            settings.auth_jwt_secret,
            algorithms=[settings.auth_jwt_algorithm],
            audience=ARTIFACT_TICKET_AUDIENCE,
            options={
                "require": [
                    "sub",
                    "project_id",
                    "mix_id",
                    "artifact_id",
                    "scope",
                    "exp",
                ]
            },
        )
        if (
            claims["scope"] != "artifact:read"
            or claims["mix_id"] != mix_id
            or claims["artifact_id"] != artifact_id
        ):
            raise ValueError("Artifact ticket scope mismatch")
        return CurrentPrincipal(user_id=claims["sub"], project_id=claims["project_id"])
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        raise ValueError("Invalid artifact ticket") from None
