from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import json

from ...db.session import get_db
from ...models.media import Mix
from ...models.analysis import AnalysisResult
from ...models.tracklist import TrackSegment, TrackMatch
from ...schemas.mix import MixOut, MixListResponse, MixUpdateRequest
from ...schemas.analysis import AnalysisResultOut
from ...schemas.tracklist import TracklistResponse, TrackSegmentOut

router = APIRouter()


@router.get("", response_model=MixListResponse)
def list_mixes(db: Session = Depends(get_db)):
    """List all analyzed and registered DJ mixes."""
    mixes = db.query(Mix).order_by(Mix.created_at.desc()).all()
    return MixListResponse(total=len(mixes), items=mixes)


@router.get("/{mix_id}", response_model=MixOut)
def get_mix(mix_id: str, db: Session = Depends(get_db)):
    """Get metadata for a specific mix."""
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


@router.get("/{mix_id}/tracklist", response_model=TracklistResponse)
def get_mix_tracklist(mix_id: str, db: Session = Depends(get_db)):
    """Retrieve detected track segments and identified song metadata for a mix."""
    mix = db.query(Mix).filter(Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found")

    segments = db.query(TrackSegment).filter(TrackSegment.mix_id == mix_id).order_by(TrackSegment.segment_index.asc()).all()
    identified_count = sum(1 for s in segments if s.match is not None)

    return TracklistResponse(
        mix_id=mix_id,
        total_tracks=len(segments),
        identified_tracks=identified_count,
        tracks=segments,
    )


@router.patch("/{mix_id}", response_model=MixOut)
def update_mix(mix_id: str, req: MixUpdateRequest, db: Session = Depends(get_db)):
    """Update title or artist metadata for a mix."""
    mix = db.query(Mix).filter(Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found")

    if req.title is not None:
        mix.title = req.title
    if req.artist is not None:
        mix.artist = req.artist

    db.commit()
    db.refresh(mix)
    return mix


@router.delete("/{mix_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mix(mix_id: str, db: Session = Depends(get_db)):
    """Delete a mix and its associated database records."""
    mix = db.query(Mix).filter(Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found")

    db.delete(mix)
    db.commit()
    return None
