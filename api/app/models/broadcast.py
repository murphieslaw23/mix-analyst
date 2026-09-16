"""AzuraCast broadcast sync models."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from api.app.db.session import Base


class BroadcastSync(Base):
    __tablename__ = "broadcast_syncs"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    media_id: Mapped[str] = mapped_column(String, ForeignKey("mixes.id"), index=True)
    station_id: Mapped[str] = mapped_column(String, default="syco23_live")
    playlist_name: Mapped[str] = mapped_column(
        String, default="Underground Freetekno Sets"
    )
    status: Mapped[str] = mapped_column(String, default="pending")
    azuracast_media_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cue_markers_synced: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
