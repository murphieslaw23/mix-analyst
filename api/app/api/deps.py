from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.job import Job
from ..models.media import Mix, UploadSession
from ..schemas.auth import CurrentPrincipal
from ..services.auth import decode_principal_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentPrincipal:
    """Require an HS256 bearer token issued by this server's configured secret."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return decode_principal_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def require_owned_mix(db: Session, principal: CurrentPrincipal, mix_id: str) -> Mix:
    mix = db.scalar(select(Mix).where(Mix.id == mix_id, Mix.project_id == principal.project_id))
    if mix is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found")
    return mix


def require_owned_job(db: Session, principal: CurrentPrincipal, job_id: str) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.project_id == principal.project_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def require_owned_upload_session(db: Session, principal: CurrentPrincipal, upload_id: str) -> UploadSession:
    upload_session = db.scalar(
        select(UploadSession).where(
            UploadSession.id == upload_id,
            UploadSession.project_id == principal.project_id,
        )
    )
    if upload_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found")
    return upload_session
