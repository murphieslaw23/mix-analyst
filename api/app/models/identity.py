from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from ..db.session import Base


class User(Base):
    __tablename__ = "users"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    projects: list[Project] = relationship(
        "Project", back_populates="owner", uselist=True
    )


class Project(Base):
    __tablename__ = "projects"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: str = Column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    owner: User = relationship("User", back_populates="projects")
