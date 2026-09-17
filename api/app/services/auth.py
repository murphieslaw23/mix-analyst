"""Authenticated ownership: JWT principals with API-key appliance fallback.

Modes:
- Open/appliance (default): no Bearer token required. Requests run as the
  default project principal; mutation endpoints additionally honor the
  existing X-API-Key gate via require_api_key.
- Enforced (AUTH_ENFORCED=true): every request needs a valid Bearer JWT.

A correctly signed token is not enough on its own: the users/projects
tables stay the authority for current membership, so a token naming a
foreign project is rejected.
"""

import jwt
from fastapi import HTTPException, Request, status
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models.identity import DEFAULT_PROJECT_ID, DEFAULT_USER_ID, Project, User
from ..models.job import Job
from ..models.media import Mix, UploadSession
from ..schemas.auth import CurrentPrincipal

BEARER_PREFIX = "bearer "


def decode_principal_token(token: str) -> CurrentPrincipal:
    """Validate a signed bearer token and extract its project selection."""
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


def check_project_membership(db: Session, principal: CurrentPrincipal) -> bool:
    """True when the principal's user still owns the principal's project."""
    return (
        db.scalar(
            select(Project.id).where(
                Project.id == principal.project_id,
                Project.owner_id == principal.user_id,
            )
        )
        is not None
    )


def default_principal() -> CurrentPrincipal:
    return CurrentPrincipal(user_id=DEFAULT_USER_ID, project_id=DEFAULT_PROJECT_ID)


def resolve_principal(request: Request | None, db: Session) -> CurrentPrincipal:
    """Authenticate one request (pure apart from the membership lookup)."""
    raw = (request.headers.get("Authorization", "") if request else "").strip()
    if raw.lower().startswith(BEARER_PREFIX):
        try:
            principal = decode_principal_token(raw[len(BEARER_PREFIX) :].strip())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
            )
        if not check_project_membership(db, principal):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token project membership is invalid",
            )
        return principal
    if settings.auth_enforced:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication required",
        )
    return default_principal()


def require_owned_mix(db: Session, principal: CurrentPrincipal, mix_id: str) -> Mix:
    """Load a mix in scope; foreign or missing ids are indistinguishable 404s."""
    mix = (
        db.query(Mix)
        .filter(Mix.id == mix_id, Mix.project_id == principal.project_id)
        .first()
    )
    if not mix:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found"
        )
    return mix


def require_owned_job(db: Session, principal: CurrentPrincipal, job_id: str) -> Job:
    """Load a job in scope; foreign or missing ids are indistinguishable 404s."""
    job = (
        db.query(Job)
        .filter(Job.id == job_id, Job.project_id == principal.project_id)
        .first()
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return job


def require_owned_upload_session(
    db: Session, principal: CurrentPrincipal, upload_id: str
) -> UploadSession:
    session = (
        db.query(UploadSession)
        .filter(
            UploadSession.id == upload_id,
            UploadSession.project_id == principal.project_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found"
        )
    return session


def ensure_default_project(db: Session) -> None:
    """Bootstrap the appliance identity (idempotent; used by the migration too)."""
    if db.get(User, DEFAULT_USER_ID) is None:
        db.add(User(id=DEFAULT_USER_ID))
    if db.get(Project, DEFAULT_PROJECT_ID) is None:
        db.add(Project(id=DEFAULT_PROJECT_ID, owner_id=DEFAULT_USER_ID))
    db.commit()
