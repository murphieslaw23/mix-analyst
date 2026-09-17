import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base
from .identity import DEFAULT_PROJECT_ID


class Batch(Base):
    """Durable parent for one fan-out of analysis child jobs."""

    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), default=DEFAULT_PROJECT_ID, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
