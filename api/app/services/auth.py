import jwt
from jwt import InvalidTokenError

from ..config import settings
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
