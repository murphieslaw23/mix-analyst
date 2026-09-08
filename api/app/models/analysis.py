from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ..db.session import Base

if TYPE_CHECKING:
    from .media import Mix


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mix_id: str = Column(
        String(36), ForeignKey("mixes.id"), nullable=False, unique=True, index=True
    )
    media_asset_id: str = Column(
        String(36), ForeignKey("media_assets.id"), nullable=False
    )

    # Tempo / BPM
    primary_bpm: float = Column(Float, nullable=False)
    bpm_confidence: float = Column(Float, nullable=False)
    bpm_candidates: str | None = Column(Text, nullable=True)

    # Key / Camelot
    detected_key: str = Column(String(50), nullable=False)
    camelot_code: str = Column(String(10), nullable=False)
    key_confidence: float = Column(Float, nullable=False)

    # Loudness / Dynamics (EBU R128)
    integrated_lufs: float = Column(Float, nullable=False)
    loudness_range_lra: float = Column(Float, nullable=False)
    true_peak_db: float = Column(Float, nullable=False)

    # Spectral & Quality Findings
    spectral_summary: str | None = Column(Text, nullable=True)
    quality_findings: str | None = Column(Text, nullable=True)

    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    mix: Mix = relationship("Mix", back_populates="analysis_result")
