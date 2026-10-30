"""The company registry: target ATS boards the app pulls on every scan.

Companies arrive two ways:
- the user adds a company they want to track (name + ATS + slug), or
- the app auto-discovers them from job URLs it has already seen (Part 2B).

Rules:
- dedupe by (ats, slug) — one board per company
- drop a board after 3 consecutive empty/broken results
- never raise: a registry problem must not sink a scan
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ats import ATS_KINDS, detect_ats, fetch_board
from .models import Company

# Empty or broken for this many consecutive scans -> disabled.
DROP_AFTER_FAILURES = 3


def normalize_ats(ats: str) -> str | None:
    a = (ats or "").lower().strip()
    return a if a in ATS_KINDS else None


def add_company(
    db: Session, name: str, ats: str, slug: str, auto_added: bool = False
) -> tuple[Company | None, bool]:
    """Add or find a company board. Returns (company, created). Dedupes on
    (ats, slug)."""
    ats = normalize_ats(ats)
    slug = (slug or "").strip()
    if not ats or not slug:
        return None, False
    name = (name or "").strip() or slug
    existing = db.scalars(
        select(Company).where(Company.ats == ats, Company.slug == slug)
    ).first()
    if existing:
        if not existing.name or existing.name == existing.slug:
            existing.name = name
        return existing, False
    c = Company(name=name, ats=ats, slug=slug, auto_added=auto_added)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c, True


def enabled_companies(db: Session) -> list[Company]:
    return list(
        db.scalars(
            select(Company)
            .where(Company.enabled == True)  # noqa: E712
            .order_by(Company.name)
        ).all()
    )


def record_result(db: Session, company: Company, ok: bool) -> None:
    company.last_checked = datetime.now(timezone.utc)
    if ok:
        company.consecutive_failures = 0
    else:
        company.consecutive_failures = (company.consecutive_failures or 0) + 1
    db.commit()


def drop_after_failures(db: Session, threshold: int = DROP_AFTER_FAILURES) -> int:
    """Disable boards that have failed `threshold` scans in a row."""
    failing = db.scalars(
        select(Company).where(
            Company.enabled == True,  # noqa: E712
            Company.consecutive_failures >= threshold,
        )
    ).all()
    for c in failing:
        c.enabled = False
    if failing:
        db.commit()
    return len(failing)


def fetch_registry_jobs(db: Session, on_progress=None) -> list[dict]:
    """Pull every enabled company board. Returns the combined job list and
    records per-board health (empty or broken both count as a failure)."""
    jobs: list[dict] = []
    for c in enabled_companies(db):
        batch = fetch_board(c.ats, c.slug)
        record_result(db, c, bool(batch))
        for j in batch:
            jobs.append(j)
        if on_progress:
            on_progress(f"company:{c.ats}:{c.slug}", len(batch), len(jobs))
    return jobs


def auto_add_from_jobs(db: Session, jobs: list[dict]) -> int:
    """Find ATS boards among already-seen job URLs and add them to the registry.

    Returns how many companies were newly added."""
    added = 0
    for j in jobs or []:
        url = (j.get("url") or "").strip()
        kind, slug = detect_ats(url)
        if not kind or not slug:
            continue
        _, created = add_company(
            db, (j.get("company") or "").strip(), kind, slug, auto_added=True
        )
        if created:
            added += 1
    return added
