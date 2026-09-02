from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import json

from ...db.session import get_db
from ..deps import get_current_principal, require_owned_mix
from ...models.media import Mix
from ...models.analysis import AnalysisResult
from ...models.tracklist import TrackSegment, TrackMatch
from ...models.transition import TransitionEvent
from ...models.artifact import Artifact
from ...config import settings
from ...services.storage import StorageService
from ...schemas.mix import MixOut, MixListResponse, MixUpdateRequest
from ...schemas.analysis import AnalysisResultOut
from ...schemas.tracklist import TracklistResponse
from ...schemas.transition import TransitionListResponse, TransitionEventOut
from ...schemas.auth import CurrentPrincipal

router = APIRouter()


def _artifact_out(artifact: Artifact, mix_id: str) -> dict:
    """Expose an opaque key and a protected API URL, never a storage path."""
    return {
        "id": artifact.id,
        "role": artifact.role,
        "key": artifact.key,
        "sha256": artifact.sha256,
        "algorithm_version": artifact.algorithm_version,
        "media_type": artifact.media_type,
        "byte_length": artifact.byte_length,
        "report": artifact.report,
        "download_url": f"{settings.api_v1_prefix}/mixes/{mix_id}/artifacts/{artifact.id}/download",
        "created_at": artifact.created_at,
    }


def _present_mix(mix: Mix) -> dict:
    artifacts = sorted(mix.artifacts, key=lambda artifact: (artifact.created_at, artifact.id))
    metadata = next((artifact for artifact in reversed(artifacts) if artifact.role == "metadata"), None)
    suggested_name = (metadata.report or {}).get("suggested_download_name") if metadata else None
    return {
        "id": mix.id,
        "title": mix.title,
        "artist": mix.artist,
        "status": mix.status,
        "created_at": mix.created_at,
        "updated_at": mix.updated_at,
        "media_asset": mix.media_asset,
        "analysis_result": mix.analysis_result,
        "artifacts": [_artifact_out(artifact, mix.id) for artifact in artifacts],
        "suggested_download_name": suggested_name,
    }


@router.get("", response_model=MixListResponse)
def list_mixes(
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """List all analyzed and registered DJ mixes."""
    mixes = db.query(Mix).filter(Mix.project_id == principal.project_id).order_by(Mix.created_at.desc()).all()
    return MixListResponse(total=len(mixes), items=[_present_mix(mix) for mix in mixes])


@router.get("/{mix_id}", response_model=MixOut)
def get_mix(
    mix_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Get metadata for a specific mix."""
    return _present_mix(require_owned_mix(db, principal, mix_id))


@router.get("/{mix_id}/artifacts/{artifact_id}/download")
def download_artifact(
    mix_id: str,
    artifact_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Serve an artifact only after project-scoped authorization.

    This is the local-storage equivalent of a signed artifact URL: the API is
    the authorization boundary and no filesystem path or unauthenticated object
    URL is disclosed to clients.
    """
    mix = require_owned_mix(db, principal, mix_id)
    artifact = db.query(Artifact).filter(
        Artifact.id == artifact_id,
        Artifact.mix_id == mix.id,
        Artifact.project_id == principal.project_id,
    ).first()
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    if not artifact.key.startswith(f"projects/{principal.project_id}/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    try:
        path = StorageService(settings.storage_root).object_path(artifact.key)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found") from None
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact is unavailable")
    metadata = next((item for item in mix.artifacts if item.role == "metadata"), None)
    suggested_name = (metadata.report or {}).get("suggested_download_name") if metadata else None
    filename = suggested_name if artifact.role == "source" and suggested_name else f"{artifact.role}-{artifact.sha256[:12]}"
    if artifact.media_type == "application/json" and not filename.endswith(".json"):
        filename = f"{filename}.json"
    return FileResponse(path, media_type=artifact.media_type, filename=filename)


@router.get("/{mix_id}/analysis", response_model=AnalysisResultOut)
def get_mix_analysis(
    mix_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Retrieve full audio analysis metrics (BPM, key, Camelot, loudness, quality) for a mix."""
    require_owned_mix(db, principal, mix_id)
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
def get_mix_tracklist(
    mix_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Retrieve detected track segments and identified song metadata for a mix."""
    require_owned_mix(db, principal, mix_id)

    segments = db.query(TrackSegment).filter(TrackSegment.mix_id == mix_id).order_by(TrackSegment.segment_index.asc()).all()
    identified_count = sum(1 for s in segments if s.match is not None)

    return TracklistResponse(
        mix_id=mix_id,
        total_tracks=len(segments),
        identified_tracks=identified_count,
        tracks=segments,
    )


@router.get("/{mix_id}/transitions", response_model=TransitionListResponse)
def get_mix_transitions(
    mix_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Retrieve detected transition blend regions, cue points, and harmonic compatibility."""
    require_owned_mix(db, principal, mix_id)

    transitions = db.query(TransitionEvent).filter(TransitionEvent.mix_id == mix_id).order_by(TransitionEvent.transition_index.asc()).all()

    return TransitionListResponse(
        mix_id=mix_id,
        total_transitions=len(transitions),
        transitions=transitions,
    )


@router.patch("/{mix_id}", response_model=MixOut)
def update_mix(
    mix_id: str,
    req: MixUpdateRequest,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Update title or artist metadata for a mix."""
    mix = require_owned_mix(db, principal, mix_id)

    if req.title is not None:
        mix.title = req.title
    if req.artist is not None:
        mix.artist = req.artist

    db.commit()
    db.refresh(mix)
    return _present_mix(mix)


@router.delete("/{mix_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mix(
    mix_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Delete a mix and its associated database records."""
    mix = require_owned_mix(db, principal, mix_id)

    db.delete(mix)
    db.commit()
    return None
