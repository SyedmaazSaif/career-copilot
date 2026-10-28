"""Search settings: what to search for, which boards, and custom sources."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import taxonomy
from ..db import get_db
from ..models import CustomSource, Job, SearchConfig
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
_CATEGORY_CODES = {row["code"] for row in taxonomy.category_list()}


def _config_out(config: SearchConfig) -> SearchConfigOut:
    return SearchConfigOut(
        queries=config.queries or [],
        enabled_sources=config.enabled_sources or [],
        all_sources=ALL_SOURCES,
        preferred_arrangements=config.preferred_arrangements
        or ["remote", "hybrid", "onsite"],
        locations=config.locations or [],
        shown_categories=config.shown_categories or [],
        excluded_categories=config.excluded_categories or [],
        company_block_list=config.company_block_list or [],
        max_age_days=config.max_age_days if config.max_age_days is not None else 30,
        all_categories=taxonomy.category_list(),
    )


@router.get("/search", response_model=SearchConfigOut)
def get_search_config(db: Session = Depends(get_db)):
    return _config_out(_get_or_seed(db))


@router.put("/search", response_model=SearchConfigOut)
def update_search_config(payload: SearchConfigIn, db: Session = Depends(get_db)):
    config = _get_or_seed(db)
    # keep only known sources, drop blank queries
    config.queries = [q.strip() for q in payload.queries if q.strip()]
    config.enabled_sources = [s for s in payload.enabled_sources if s in ALL_SOURCES]
    arr = [a for a in payload.preferred_arrangements if a in _ARRANGEMENTS]
    config.preferred_arrangements = arr or ["remote", "hybrid", "onsite"]
    config.locations = [loc.strip() for loc in payload.locations if loc.strip()]
    config.shown_categories = [
        c for c in payload.shown_categories if c in _CATEGORY_CODES
    ]
    config.excluded_categories = [
        c for c in payload.excluded_categories if c in _CATEGORY_CODES
    ]
    config.company_block_list = sorted(
        {c.strip() for c in payload.company_block_list if c.strip()}
    )
    config.max_age_days = max(0, min(int(payload.max_age_days or 0), 365))
    db.commit()

    # Scoring reads the arrangements, the locations and the search terms, so a
    # settings change that did not rescore would leave the user looking at a
    # list ranked by the settings they just replaced.
    _rescore_all(db)

    db.refresh(config)
    return _config_out(config)


def _rescore_all(db: Session) -> None:
    """Re-run scoring over every stored job against the current settings."""
    from ..matching import build_profile, score_job

    profile = build_profile(db)
    for job in db.scalars(select(Job)).all():
        result = score_job(
            {
                "title": job.title,
                "description": job.description,
                "location": job.location,
                "tags": job.tags or [],
            },
            profile,
        )
        job.score = result["score"]
        job.score_reason = result["reason"]
        job.red_flags = result["red_flags"]
        job.explanations = result["explanations"]
        job.work_type = result["work_type"]
        job.employment_type = result["employment_type"]
        job.score_version = result["score_version"]
    db.commit()


# ---- Custom sources (user-added job boards / feeds) ----
_KINDS = {"rss", "greenhouse", "lever", "ashby", "company", "url"}


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
