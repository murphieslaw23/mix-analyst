import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from ..db.session import Base


class OutboxMessage(Base):
    """A committed command that has not necessarily reached the broker yet."""

    __tablename__ = "outbox_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    aggregate_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    kind = Column(String(100), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    delivery_attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True, index=True)

    job = relationship("Job", back_populates="outbox_messages")
