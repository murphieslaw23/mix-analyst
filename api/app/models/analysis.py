import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship

from ..db.session import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mix_id = Column(String(36), ForeignKey("mixes.id"), nullable=False, unique=True, index=True)
    media_asset_id = Column(String(36), ForeignKey("media_assets.id"), nullable=False)

    # Tempo / BPM
    primary_bpm = Column(Float, nullable=False)
    bpm_confidence = Column(Float, nullable=False)
    bpm_candidates = Column(Text, nullable=True)  # JSON list of candidate hypotheses

    # Key / Camelot
    detected_key = Column(String(50), nullable=False)
    camelot_code = Column(String(10), nullable=False)
    key_confidence = Column(Float, nullable=False)

    # Loudness / Dynamics (EBU R128)
    integrated_lufs = Column(Float, nullable=False)
    loudness_range_lra = Column(Float, nullable=False)
    true_peak_db = Column(Float, nullable=False)

    # Spectral & Quality Findings
    spectral_summary = Column(Text, nullable=True)  # JSON map of frequency bands
    quality_findings = Column(Text, nullable=True)  # JSON list of detected defects

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    mix = relationship("Mix", back_populates="analysis_result")
