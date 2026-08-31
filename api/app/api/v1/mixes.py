from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import json

from ...db.session import get_db
from ...models.media import Mix
from ...models.analysis import AnalysisResult
from ...schemas.mix import MixOut, MixListResponse, MixUpdateRequest
from ...schemas.analysis import AnalysisResultOut

router = APIRouter()


@router.get("", response_model=MixListResponse)
def list_mixes(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List all analyzed and registered mixes."""
    total = db.query(Mix).count()
    items = db.query(Mix).order_by(Mix.created_at.desc()).offset(skip).limit(limit).all()
    return MixListResponse(items=items, total=total)


@router.get("/{mix_id}", response_model=MixOut)
def get_mix(mix_id: str, db: Session = Depends(get_db)):
    """Get details of a specific mix and its underlying media asset."""
    mix = db.query(Mix).filter(Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found")
    return mix


@router.get("/{mix_id}/analysis", response_model=AnalysisResultOut)
def get_mix_analysis(mix_id: str, db: Session = Depends(get_db)):
    """Retrieve full audio analysis metrics (BPM, key, Camelot, loudness, quality) for a mix."""
    analysis = db.query(AnalysisResult).filter(AnalysisResult.mix_id == mix_id).first()
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis results not found for this mix")

    bpm_cand = json.loads(analysis.bpm_candidates) if analysis.bpm_candidates else []
    spectral = json.loads(analysis.spectral_summary) if analysis.spectral_summary else {}
    quality = json.loads(analysis.quality_findings) if analysis.quality_findings else []

    return AnalysisResultOut(
        id=analysis.id,
        mix_id=analysis.mix_id,
        media_asset_id=analysis.media_asset_id,
        primary_bpm=analysis.primary_bpm,
        bpm_confidence=analysis.bpm_confidence,
        bpm_candidates=bpm_cand,
        detected_key=analysis.detected_key,
        camelot_code=analysis.camelot_code,
        key_confidence=analysis.key_confidence,
        integrated_lufs=analysis.integrated_lufs,
        loudness_range_lra=analysis.loudness_range_lra,
        true_peak_db=analysis.true_peak_db,
        spectral_summary=spectral,
        quality_findings=quality,
        created_at=analysis.created_at,
    )


@router.patch("/{mix_id}", response_model=MixOut)
def update_mix(mix_id: str, req: MixUpdateRequest, db: Session = Depends(get_db)):
    """Update title or artist metadata for a mix."""
    mix = db.query(Mix).filter(Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found")

    if req.title is not None:
        mix.title = req.title.strip()
    if req.artist is not None:
        mix.artist = req.artist.strip()

    db.commit()
    db.refresh(mix)
    return mix
