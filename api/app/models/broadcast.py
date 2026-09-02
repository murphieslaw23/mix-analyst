"""AzuraCast broadcast sync models."""
from sqlalchemy import Column, String, Float, Integer, ForeignKey, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from api.app.db.session import Base

class BroadcastSync(Base):
    __tablename__ = "broadcast_syncs"

    id = Column(String, primary_key=True, index=True)
    media_id = Column(String, ForeignKey("media_assets.id"), nullable=False, index=True)
    station_id = Column(String, default="syco23_live")
    playlist_name = Column(String, default="Underground Freetekno Sets")
    status = Column(String, default="pending")  # pending, synced, broadcasting, completed, failed
    azuracast_media_id = Column(String, nullable=True)
    cue_markers_synced = Column(Integer, default=0)
    scheduled_start = Column(DateTime(timezone=True), nullable=True)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    synced_at = Column(DateTime(timezone=True), nullable=True)
