from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import json

from ...db.session import get_db
from ...config import settings
from ...models.media import Mix
from ...models.analysis import AnalysisResult
from ...models.tracklist import TrackSegment, TrackMatch
from ...models.transition import TransitionEvent
from ...schemas.mix import (
    MixOut,
    MixDetailOut,
    MixListResponse,
    MixUpdateRequest,
    MixTrackOut,
    MixTransitionOut,
)
from ...schemas.analysis import AnalysisResultOut
from ...schemas.tracklist import TracklistResponse
from ...schemas.transition import TransitionListResponse, TransitionEventOut
from ...services.storage import StorageService

router = APIRouter()

AUDIO_MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".wave": "audio/wav",
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".opus": "audio/ogg",
}


@router.get("", response_model=MixListResponse)
def list_mixes(db: Session = Depends(get_db)):
    """List all analyzed and registered DJ mixes."""
    mixes = db.query(Mix).order_by(Mix.created_at.desc()).all()
    return MixListResponse(total=len(mixes), items=mixes)


def _build_mix_detail(mix: Mix, db: Session) -> MixDetailOut:
    """Assemble the full PWA payload: metadata, audio URL, cues, transitions."""
    asset = mix.media_asset
    analysis = db.query(AnalysisResult).filter(AnalysisResult.mix_id == mix.id).first()

    segments = (
        db.query(TrackSegment)
        .filter(TrackSegment.mix_id == mix.id)
        .order_by(TrackSegment.segment_index.asc())
        .all()
    )
    tracks = [
        MixTrackOut(
            id=seg.id,
            title=seg.match.title if seg.match else "Unknown Track",
            artist=seg.match.artist if seg.match else "Unknown Artist",
            start_time=seg.start_time_seconds,
            end_time=seg.end_time_seconds,
            bpm=analysis.primary_bpm if analysis else None,
            camelot_key=analysis.camelot_code if analysis else None,
        )
        for seg in segments
    ]

    events = (
        db.query(TransitionEvent)
        .filter(TransitionEvent.mix_id == mix.id)
        .order_by(TransitionEvent.transition_index.asc())
        .all()
    )
    transitions = [
        MixTransitionOut(
            id=ev.id,
            start_time=ev.start_time_seconds,
            end_time=ev.end_time_seconds,
            transition_type=ev.transition_type,
            from_key=None,
            to_key=None,
            harmonic_compatibility=ev.camelot_compatibility,
        )
        for ev in events
    ]

    return MixDetailOut(
        id=mix.id,
        title=mix.title,
        artist=mix.artist,
        status=mix.status,
        created_at=mix.created_at,
        updated_at=mix.updated_at,
        original_filename=asset.original_filename,
        duration_seconds=asset.duration_seconds,
        bpm=analysis.primary_bpm if analysis else None,
        camelot_key=analysis.camelot_code if analysis else None,
        audio_url=f"{settings.api_v1_prefix}/mixes/{mix.id}/audio",
        tracks=tracks,
        transitions=transitions,
    )


@router.get("/{mix_id}", response_model=MixDetailOut)
def get_mix(mix_id: str, db: Session = Depends(get_db)):
    """Get full metadata, audio URL, track cues and transitions for a mix."""
    mix = db.query(Mix).filter(Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found")
    return _build_mix_detail(mix, db)


@router.get("/{mix_id}/audio")
def stream_mix_audio(mix_id: str, db: Session = Depends(get_db)):
    """Stream the original mix audio file (supports HTTP Range seeks)."""
    mix = db.query(Mix).filter(Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found")

    storage = StorageService(settings.storage_root)
    try:
        abs_path = storage.safe_resolve(mix.media_asset.storage_path)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Stored audio path is invalid")
    if not abs_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found on storage")

    suffix = abs_path.suffix.lower()
    return FileResponse(
        path=str(abs_path),
        media_type=AUDIO_MEDIA_TYPES.get(suffix, "application/octet-stream"),
        filename=mix.media_asset.original_filename,
    )


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


@router.get("/{mix_id}/transitions", response_model=TransitionListResponse)
def get_mix_transitions(mix_id: str, db: Session = Depends(get_db)):
    """Retrieve detected transition blend regions, cue points, and harmonic compatibility."""
    mix = db.query(Mix).filter(Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mix not found")

    transitions = db.query(TransitionEvent).filter(TransitionEvent.mix_id == mix_id).order_by(TransitionEvent.transition_index.asc()).all()

    return TransitionListResponse(
        mix_id=mix_id,
        total_transitions=len(transitions),
        transitions=transitions,
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
