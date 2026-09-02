"""Durable immutable artifacts owned by a project and attached to a mix."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.session import Base


class Artifact(Base):
    __tablename__ = "artifacts"
    # Object keys identify immutable physical bytes within a project, while a
    # row is an attachment of those bytes to one mix. Multiple mixes may share
    # a deduplicated source and its deterministic derived artifacts.
    __table_args__ = (UniqueConstraint("project_id", "mix_id", "key", name="uq_artifacts_project_mix_key"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    mix_id = Column(String(36), ForeignKey("mixes.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False)
    key = Column(String(512), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    algorithm_version = Column(String(100), nullable=False)
    media_type = Column(String(100), nullable=False)
    byte_length = Column(BigInteger, nullable=False)
    report = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    mix = relationship("Mix", back_populates="artifacts")
