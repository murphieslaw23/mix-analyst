import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .job import Job


class OutboxMessage(Base):
    """A committed command not yet accepted by the broker.

    Queuing happens only through these rows: the API transaction commits
    the job *and* its outbox record atomically, so a broker failure can
    never lose a queued job — the dispatcher retries the pending row.
    """

    __tablename__ = "outbox_messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    aggregate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id"), index=True
    )
    kind: Mapped[str] = mapped_column(String(100), default="job.dispatch", index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    job: Mapped["Job"] = relationship(back_populates="outbox_messages")

    def payload_dict(self) -> dict[str, Any]:
        import json

        try:
            data = json.loads(self.payload)
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
