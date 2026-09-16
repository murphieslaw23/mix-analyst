"""Export endpoints for CUE sheets, Rekordbox XML, Traktor NML, and YouTube tracklists."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from api.app.db.session import get_db
from api.app.models.media import Mix
from api.app.models.analysis import AnalysisResult
from api.app.models.tracklist import TrackSegment
from api.app.models.transition import TransitionEvent
from api.app.services.export_service import ExportService

router = APIRouter()

DEFAULT_EXPORT_BPM = 128.0


def _get_mix_or_404(db: Session, mix_id: str) -> Mix:
    mix = db.query(Mix).filter(Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(status_code=404, detail="Mix not found")
    return mix


def _get_mix_bpm(db: Session, mix_id: str) -> float:
    """Use the analyzed primary BPM; fall back to 128 only when unanalyzed."""
    analysis = db.query(AnalysisResult).filter(AnalysisResult.mix_id == mix_id).first()
    if analysis and analysis.primary_bpm:
        return float(analysis.primary_bpm)
    return DEFAULT_EXPORT_BPM


def _get_tracks(db: Session, mix_id: str) -> list[dict]:
    segments = db.query(TrackSegment).filter(TrackSegment.mix_id == mix_id).order_by(TrackSegment.segment_index).all()
    return [
        {
            "title": segment.match.title if segment.match else "Unknown Track",
            "artist": segment.match.artist if segment.match else "Unknown Artist",
            "start_time": segment.start_time_seconds,
        }
        for segment in segments
    ]


@router.get("/{mix_id}/export/cue")
def export_cue_sheet(mix_id: str, db: Session = Depends(get_db)):
    mix = _get_mix_or_404(db, mix_id)
    cue_content = ExportService.generate_cue_sheet(
        filename=mix.media_asset.original_filename,
        title=mix.title,
        performer=mix.artist or "SYCO23",
        tracks=_get_tracks(db, mix_id),
    )
    return Response(content=cue_content, media_type="application/x-cue", headers={"Content-Disposition": f'attachment; filename="{mix.id}.cue"'})


@router.get("/{mix_id}/export/youtube")
def export_youtube_timestamps(mix_id: str, db: Session = Depends(get_db)):
    _get_mix_or_404(db, mix_id)
    return Response(content=ExportService.generate_youtube_timestamps(_get_tracks(db, mix_id)), media_type="text/plain; charset=utf-8")


@router.get("/{mix_id}/export/rekordbox")
def export_rekordbox(mix_id: str, db: Session = Depends(get_db)):
    mix = _get_mix_or_404(db, mix_id)
    transitions = [
        {"start_time": event.start_time_seconds, "transition_type": event.transition_type}
        for event in db.query(TransitionEvent).filter(TransitionEvent.mix_id == mix_id).order_by(TransitionEvent.transition_index).all()
    ]
    xml_content = ExportService.generate_rekordbox_xml(
        mix_id=mix.id,
        title=mix.title,
        file_path=mix.media_asset.storage_path,
        duration=mix.media_asset.duration_seconds,
        bpm=_get_mix_bpm(db, mix_id),
        tracks=_get_tracks(db, mix_id),
        transitions=transitions,
    )
    return Response(content=xml_content, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{mix.id}_rekordbox.xml"'})


@router.get("/{mix_id}/export/traktor")
def export_traktor(mix_id: str, db: Session = Depends(get_db)):
    mix = _get_mix_or_404(db, mix_id)
    nml_content = ExportService.generate_traktor_nml(
        title=mix.title,
        file_path=mix.media_asset.storage_path,
        duration=mix.media_asset.duration_seconds,
        bpm=_get_mix_bpm(db, mix_id),
        tracks=_get_tracks(db, mix_id),
    )
    return Response(content=nml_content, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{mix.id}_traktor.nml"'})
