import jwt
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models.identity import Project, User
from ..schemas.auth import CurrentPrincipal


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


def require_persisted_project_membership(db: Session, principal: CurrentPrincipal) -> CurrentPrincipal:
    """Ensure a correctly signed claim names a project actually owned by its user.

    JWT signatures establish who issued a token; the database remains the
    authority for current user/project membership.  This prevents a token
    minted with an otherwise valid signature from choosing another tenant.
    """
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
