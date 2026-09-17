"""Immutable artifact registration with deterministic identity."""

from sqlalchemy.orm import Session

from ..models.artifact import Artifact


def artifact_key(source_sha256: str, role: str, algorithm_version: str) -> str:
    """Content-addressed storage key shared by storage layout and DB row."""
    return f"artifacts/{role}/{algorithm_version}/{source_sha256}"


def register_artifact(
    db: Session,
    *,
    project_id: str,
    mix_id: str | None,
    role: str,
    key: str,
    sha256: str,
    algorithm_version: str,
    media_type: str,
    byte_length: int,
) -> Artifact:
    """Get-or-create by storage key: repeats reuse the same identity."""
    existing = db.query(Artifact).filter(Artifact.key == key).first()
    if existing:
        return existing
    row = Artifact(
        project_id=project_id,
        mix_id=mix_id,
        role=role,
        key=key,
        sha256=sha256,
        algorithm_version=algorithm_version,
        media_type=media_type,
        byte_length=byte_length,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
