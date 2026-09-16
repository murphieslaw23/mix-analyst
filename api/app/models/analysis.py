import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .media import Mix


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    mix_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mixes.id"), unique=True, index=True
    )
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id")
    )

    # Tempo / BPM
    primary_bpm: Mapped[float] = mapped_column(Float)
    bpm_confidence: Mapped[float] = mapped_column(Float)
    bpm_candidates: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Key / Camelot
    detected_key: Mapped[str] = mapped_column(String(50))
    camelot_code: Mapped[str] = mapped_column(String(10))
    key_confidence: Mapped[float] = mapped_column(Float)

    # Loudness / Dynamics (EBU R128)
    integrated_lufs: Mapped[float] = mapped_column(Float)
    loudness_range_lra: Mapped[float] = mapped_column(Float)
    true_peak_db: Mapped[float] = mapped_column(Float)

    # Spectral & Quality Findings
    spectral_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_findings: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    mix: Mapped["Mix"] = relationship(back_populates="analysis_result")
