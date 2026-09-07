"""Search settings: what to search for, which boards, and custom sources."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CustomSource, SearchConfig
from ..scrapers import ALL_SOURCES, DEFAULT_QUERIES
from ..schemas import (
    CustomSourceIn,
    CustomSourceOut,
    SearchConfigIn,
    SearchConfigOut,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _get_or_seed(db: Session) -> SearchConfig:
    config = db.get(SearchConfig, 1)
    if config is None:
        config = SearchConfig(
            id=1,
            queries=list(DEFAULT_QUERIES),
            enabled_sources=list(ALL_SOURCES),
            known_sources=list(ALL_SOURCES),
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


_ARRANGEMENTS = {"remote", "hybrid", "onsite"}


@router.get("/search", response_model=SearchConfigOut)
def get_search_config(db: Session = Depends(get_db)):
    config = _get_or_seed(db)
    return SearchConfigOut(
        queries=config.queries or [],
        enabled_sources=config.enabled_sources or [],
        all_sources=ALL_SOURCES,
        preferred_arrangements=config.preferred_arrangements or list(_ARRANGEMENTS),
        locations=config.locations or [],
    )


@router.put("/search", response_model=SearchConfigOut)
def update_search_config(payload: SearchConfigIn, db: Session = Depends(get_db)):
    config = _get_or_seed(db)
    # keep only known sources, drop blank queries
    config.queries = [q.strip() for q in payload.queries if q.strip()]
    config.enabled_sources = [s for s in payload.enabled_sources if s in ALL_SOURCES]
    arr = [a for a in payload.preferred_arrangements if a in _ARRANGEMENTS]
    config.preferred_arrangements = arr or ["remote", "hybrid", "onsite"]
    config.locations = [loc.strip() for loc in payload.locations if loc.strip()]
    db.commit()
    db.refresh(config)
    return SearchConfigOut(
        queries=config.queries,
        enabled_sources=config.enabled_sources,
        all_sources=ALL_SOURCES,
        preferred_arrangements=config.preferred_arrangements,
        locations=config.locations or [],
    )


# ---- Custom sources (user-added job boards / feeds) ----
_KINDS = {"rss", "greenhouse", "lever", "url"}


@router.get("/sources", response_model=list[CustomSourceOut])
def list_sources(db: Session = Depends(get_db)):
    return db.scalars(select(CustomSource).order_by(CustomSource.id)).all()


@router.post("/sources", response_model=CustomSourceOut, status_code=201)
def add_source(payload: CustomSourceIn, db: Session = Depends(get_db)):
    if payload.kind not in _KINDS:
        raise HTTPException(422, f"kind must be one of {sorted(_KINDS)}")
    if not payload.value.strip():
        raise HTTPException(422, "value is required")
    src = CustomSource(
        kind=payload.kind,
        value=payload.value.strip(),
        label=payload.label.strip(),
        enabled=payload.enabled,
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


@router.put("/sources/{source_id}", response_model=CustomSourceOut)
def update_source(source_id: int, payload: CustomSourceIn, db: Session = Depends(get_db)):
    src = db.get(CustomSource, source_id)
    if src is None:
        raise HTTPException(404, "source not found")
    src.kind = payload.kind
    src.value = payload.value.strip()
    src.label = payload.label.strip()
    src.enabled = payload.enabled
    db.commit()
    db.refresh(src)
    return src


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    src = db.get(CustomSource, source_id)
    if src is None:
        raise HTTPException(404, "source not found")
    db.delete(src)
    db.commit()
