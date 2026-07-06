"""Profile singleton router. The profile is a single row (id=1), so it only
supports read and update, never create or delete."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Profile
from ..schemas import ProfileBase, ProfileOut

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    profile = db.get(Profile, 1)
    if profile is None:
        raise HTTPException(404, "profile not initialised")
    return profile


@router.put("", response_model=ProfileOut)
def update_profile(payload: ProfileBase, db: Session = Depends(get_db)):
    profile = db.get(Profile, 1)
    if profile is None:
        profile = Profile(id=1)
        db.add(profile)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile
