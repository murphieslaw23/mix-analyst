import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base
from .identity import DEFAULT_PROJECT_ID


class Artifact(Base):
    """Immutable derived artifact: content-addressed key, versioned algorithm.

    Repeat execution over the same source with the same algorithm version
    reuses the same identity instead of duplicating bytes or rows.
    """

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), default=DEFAULT_PROJECT_ID, index=True
    )
    mix_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("mixes.id"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(50), index=True)
    key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    sha256: Mapped[str] = mapped_column(String(64))
    algorithm_version: Mapped[str] = mapped_column(String(50))
    media_type: Mapped[str] = mapped_column(String(100))
    byte_length: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
