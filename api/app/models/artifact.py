"""Durable immutable artifacts owned by a project and attached to a mix."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .media import Mix


class Artifact(Base):
    __tablename__ = "artifacts"
    # Object keys identify immutable physical bytes within a project, while a
    # row is an attachment of those bytes to one mix. Multiple mixes may share
    # a deduplicated source and its deterministic derived artifacts.
    __table_args__ = (
        UniqueConstraint(
            "project_id", "mix_id", "key", name="uq_artifacts_project_mix_key"
        ),
    )

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: str = Column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    mix_id: str = Column(String(36), ForeignKey("mixes.id"), nullable=False, index=True)
    role: str = Column(String(50), nullable=False)
    key: str = Column(String(512), nullable=False)
    sha256: str = Column(String(64), nullable=False, index=True)
    algorithm_version: str = Column(String(100), nullable=False)
    media_type: str = Column(String(100), nullable=False)
    byte_length: int = Column(BigInteger, nullable=False)
    report: dict[str, Any] | None = Column(JSON, nullable=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    mix: Mix = relationship("Mix", back_populates="artifacts")
