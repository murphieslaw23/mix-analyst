"""Export endpoints for CUE sheets, Rekordbox XML, Traktor NML, and YouTube tracklists."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from api.app.db.session import get_db
from api.app.models.media import Media
from api.app.models.tracklist import Tracklist, TrackEntry
from api.app.models.transition import Transition
from api.app.services.export_service import ExportService

router = APIRouter()

@router.get("/{mix_id}/export/cue")
def export_cue_sheet(mix_id: str, db: Session = Depends(get_db)):
    """Export mix cue points as standard CUE sheet."""
    media = db.query(Media).filter(Media.id == mix_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix not found")
        
    tracklist = db.query(Tracklist).filter(Tracklist.media_id == mix_id).first()
    tracks = []
    if tracklist:
        entries = db.query(TrackEntry).filter(TrackEntry.tracklist_id == tracklist.id).order_by(TrackEntry.start_time).all()
        for e in entries:
            tracks.append({
                "title": e.title,
                "artist": e.artist,
                "start_time": e.start_time,
                "bpm": e.bpm,
                "camelot_key": e.camelot_key
            })
            
    cue_content = ExportService.generate_cue_sheet(
        filename=media.original_filename or f"{media.id}.wav",
        title=media.title or media.original_filename,
        performer="SYCO23",
        tracks=tracks
    )
    
    return Response(
        content=cue_content,
        media_type="application/x-cue",
        headers={"Content-Disposition": f'attachment; filename="{media.id}.cue"'}
    )

@router.get("/{mix_id}/export/youtube")
def export_youtube_timestamps(mix_id: str, db: Session = Depends(get_db)):
    """Export mix timestamps formatted for YouTube description."""
    media = db.query(Media).filter(Media.id == mix_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix not found")
        
    tracklist = db.query(Tracklist).filter(Tracklist.media_id == mix_id).first()
    tracks = []
    if tracklist:
        entries = db.query(TrackEntry).filter(TrackEntry.tracklist_id == tracklist.id).order_by(TrackEntry.start_time).all()
        for e in entries:
            tracks.append({
                "title": e.title,
                "artist": e.artist,
                "start_time": e.start_time,
                "bpm": e.bpm,
                "camelot_key": e.camelot_key
            })
            
    yt_text = ExportService.generate_youtube_timestamps(tracks)
    return Response(content=yt_text, media_type="text/plain; charset=utf-8")

@router.get("/{mix_id}/export/rekordbox")
def export_rekordbox(mix_id: str, db: Session = Depends(get_db)):
    """Export mix cue and transition points as Pioneer Rekordbox XML."""
    media = db.query(Media).filter(Media.id == mix_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix not found")
        
    tracklist = db.query(Tracklist).filter(Tracklist.media_id == mix_id).first()
    tracks = []
    if tracklist:
        entries = db.query(TrackEntry).filter(TrackEntry.tracklist_id == tracklist.id).order_by(TrackEntry.start_time).all()
        for e in entries:
            tracks.append({
                "title": e.title,
                "artist": e.artist,
                "start_time": e.start_time,
                "bpm": e.bpm,
                "camelot_key": e.camelot_key
            })
            
    transitions_db = db.query(Transition).filter(Transition.media_id == mix_id).order_by(Transition.start_time).all()
    transitions = []
    for t in transitions_db:
        transitions.append({
            "start_time": t.start_time,
            "transition_type": t.transition_type,
            "from_key": t.from_key,
            "to_key": t.to_key
        })
        
    xml_content = ExportService.generate_rekordbox_xml(
        mix_id=media.id,
        title=media.title or media.original_filename,
        file_path=media.storage_path or "",
        duration=media.duration_seconds or 0.0,
        bpm=128.0,
        tracks=tracks,
        transitions=transitions
    )
    
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{media.id}_rekordbox.xml"'}
    )

@router.get("/{mix_id}/export/traktor")
def export_traktor(mix_id: str, db: Session = Depends(get_db)):
    """Export mix cue points as Traktor NML."""
    media = db.query(Media).filter(Media.id == mix_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix not found")
        
    tracklist = db.query(Tracklist).filter(Tracklist.media_id == mix_id).first()
    tracks = []
    if tracklist:
        entries = db.query(TrackEntry).filter(TrackEntry.tracklist_id == tracklist.id).order_by(TrackEntry.start_time).all()
        for e in entries:
            tracks.append({
                "title": e.title,
                "artist": e.artist,
                "start_time": e.start_time,
                "bpm": e.bpm,
                "camelot_key": e.camelot_key
            })
            
    nml_content = ExportService.generate_traktor_nml(
        title=media.title or media.original_filename,
        file_path=media.storage_path or "",
        duration=media.duration_seconds or 0.0,
        bpm=128.0,
        tracks=tracks
    )
    
    return Response(
        content=nml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{media.id}_traktor.nml"'}
    )
