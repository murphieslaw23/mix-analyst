from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ...db.session import get_db
from ...models.media import Mix
from ...schemas.mix import MixOut, MixListResponse, MixUpdateRequest

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
