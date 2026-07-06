"""Experiences and their nested bullets. Bullets carry skill tags."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bullet, Experience
from ..schemas import (
    BulletCreate,
    BulletOut,
    ExperienceCreate,
    ExperienceOut,
)

router = APIRouter(prefix="/api/experiences", tags=["experiences"])


@router.get("", response_model=list[ExperienceOut])
def list_experiences(db: Session = Depends(get_db)):
    return db.scalars(
        select(Experience).order_by(Experience.sort_order, Experience.id)
    ).all()


@router.post("", response_model=ExperienceOut, status_code=201)
def create_experience(payload: ExperienceCreate, db: Session = Depends(get_db)):
    exp = Experience(**payload.model_dump())
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.put("/{exp_id}", response_model=ExperienceOut)
def update_experience(
    exp_id: int, payload: ExperienceCreate, db: Session = Depends(get_db)
):
    exp = db.get(Experience, exp_id)
    if exp is None:
        raise HTTPException(404, f"experience {exp_id} not found")
    for key, value in payload.model_dump().items():
        setattr(exp, key, value)
    db.commit()
    db.refresh(exp)
    return exp


@router.delete("/{exp_id}", status_code=204)
def delete_experience(exp_id: int, db: Session = Depends(get_db)):
    exp = db.get(Experience, exp_id)
    if exp is None:
        raise HTTPException(404, f"experience {exp_id} not found")
    db.delete(exp)  # cascade removes its bullets
    db.commit()


# ---- Bullets (nested under an experience) ----
@router.post("/{exp_id}/bullets", response_model=BulletOut, status_code=201)
def add_bullet(exp_id: int, payload: BulletCreate, db: Session = Depends(get_db)):
    exp = db.get(Experience, exp_id)
    if exp is None:
        raise HTTPException(404, f"experience {exp_id} not found")
    bullet = Bullet(experience_id=exp_id, **payload.model_dump())
    db.add(bullet)
    db.commit()
    db.refresh(bullet)
    return bullet


@router.put("/bullets/{bullet_id}", response_model=BulletOut)
def update_bullet(bullet_id: int, payload: BulletCreate, db: Session = Depends(get_db)):
    bullet = db.get(Bullet, bullet_id)
    if bullet is None:
        raise HTTPException(404, f"bullet {bullet_id} not found")
    for key, value in payload.model_dump().items():
        setattr(bullet, key, value)
    db.commit()
    db.refresh(bullet)
    return bullet


@router.delete("/bullets/{bullet_id}", status_code=204)
def delete_bullet(bullet_id: int, db: Session = Depends(get_db)):
    bullet = db.get(Bullet, bullet_id)
    if bullet is None:
        raise HTTPException(404, f"bullet {bullet_id} not found")
    db.delete(bullet)
    db.commit()
