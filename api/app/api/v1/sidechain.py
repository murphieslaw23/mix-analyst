from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.app.db.session import get_db
from api.app.models.media import Mix
from api.app.schemas.sidechain import SidechainProcessRequest

router = APIRouter()

@router.post("/mastering/sidechain")
def apply_dynamic_sidechain(request: SidechainProcessRequest, db: Session = Depends(get_db)):
    """Apply automated kick/sub-bass sidechain ducking and phase alignment."""
    media = db.query(Mix).filter(Mix.id == request.media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mix asset not found")

    # DynamicSidechainDSP is real but operates on isolated kick/bass stems,
    # which don't exist until stem separation lands. Previously this endpoint
    # processed a synthetic 5s sine pair and reported it as the mix result.
    raise HTTPException(
        status_code=501,
        detail=(
            "Sidechain processing not implemented: requires isolated "
            "kick/bass stems from the stem-separation pipeline, which is "
            "not available yet. No audio was processed."
        ),
    )
