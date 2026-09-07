import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ...config import settings
from ...db.session import get_db
from ...models.analysis import AnalysisResult
from ...models.artifact import Artifact
from ...models.media import Mix
from ...models.tracklist import TrackSegment
from ...models.transition import TransitionEvent
from ...schemas.analysis import AnalysisResultOut
from ...schemas.auth import CurrentPrincipal
from ...schemas.mix import MixListResponse, MixOut, MixUpdateRequest
from ...schemas.tracklist import TracklistResponse
from ...schemas.transition import TransitionListResponse
from ...services.auth import artifact_ticket_ttl, decode_artifact_ticket, issue_artifact_ticket
from ...services.storage import StorageService
from ..deps import get_current_principal, get_optional_principal, require_owned_mix

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


def _owned_artifact(db: Session, principal: CurrentPrincipal, mix_id: str, artifact_id: str) -> tuple[Mix, Artifact]:
    mix = require_owned_mix(db, principal, mix_id)
    artifact = db.query(Artifact).filter(
        Artifact.id == artifact_id,
        Artifact.mix_id == mix.id,
        Artifact.project_id == principal.project_id,
    ).first()
    if artifact is None or not artifact.key.startswith(f"projects/{principal.project_id}/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return mix, artifact


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


@router.post("/{mix_id}/artifacts/{artifact_id}/download-ticket")
def create_artifact_download_ticket(
    mix_id: str,
    artifact_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Mint a scoped capability so native media can stream with Range requests."""
    mix, _ = _owned_artifact(db, principal, mix_id, artifact_id)
    ttl_seconds = artifact_ticket_ttl(mix.media_asset.duration_seconds)
    ticket = issue_artifact_ticket(principal, mix_id, artifact_id, ttl_seconds=ttl_seconds)
    protected_url = f"{settings.api_v1_prefix}/mixes/{mix_id}/artifacts/{artifact_id}/download"
    return {
        "download_url": f"{protected_url}?ticket={quote(ticket, safe='')}",
        "expires_in_seconds": ttl_seconds,
    }


@router.get("/{mix_id}/artifacts/{artifact_id}/download")
def download_artifact(
    mix_id: str,
    artifact_id: str,
    ticket: str | None = None,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal | None = Depends(get_optional_principal),
):
    """Serve an artifact after bearer authorization or a scoped media ticket."""
    effective_principal = principal
    if effective_principal is None:
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            effective_principal = decode_artifact_ticket(ticket, mix_id, artifact_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid artifact ticket") from None

    mix, artifact = _owned_artifact(db, effective_principal, mix_id, artifact_id)
    try:
        path = StorageService(settings.storage_root).object_path(artifact.key)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found") from None
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact is unavailable")
    metadata = next(
        (
            item
            for item in sorted(mix.artifacts, key=lambda item: (item.created_at, item.id), reverse=True)
            if item.role == "metadata"
        ),
        None,
    )
    suggested_name = (metadata.report or {}).get("suggested_download_name") if metadata else None
    if artifact.role == "source":
        filename = mix.media_asset.original_filename
    elif artifact.role == "mastered" and suggested_name:
        filename = suggested_name
    else:
        filename = f"{artifact.role}-{artifact.sha256[:12]}"
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
    identified_count = sum(1 for segment in segments if segment.match is not None)

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
