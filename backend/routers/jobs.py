"""Jobs + CRM API: scan, list/filter, pipeline moves, analytics, run history."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import scan_manager
from ..company_site import find_company_site
from ..custom_scrapers import fetch_single_job
from ..db import get_db
from ..ingest import dedupe_key, ingest_jobs
from ..models import STAGES, DismissedJob, Job, ScrapeRun
from ..schemas import (
    AddJobByUrl,
    CompanySiteOut,
    DismissedJobOut,
    JobOut,
    JobPatch,
    ScanStatus,
    ScrapeRunOut,
)
from ..scoring import build_profile_context

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Stages that count as "the application got a response".
_RESPONDED = {"Screening", "Interview", "Offer"}


def _latest_scan_start(db: Session) -> datetime | None:
    """When the most recent completed scan started. Jobs first seen at or after
    it are 'new this scan'."""
    latest = (
        db.query(ScrapeRun)
        .filter(ScrapeRun.status == "done")
        .order_by(ScrapeRun.id.desc())
        .first()
    )
    return latest.started_at if latest else None


def _mark_new(jobs: list[Job], cutoff: datetime | None) -> list[Job]:
    """Stamp the transient is_new flag JobOut serialises. Not a stored column —
    it depends on the run history, not the row."""
    for job in jobs:
        job.is_new = bool(
            cutoff and job.first_scanned_at and job.first_scanned_at >= cutoff
        )
    return jobs


@router.post("/scan", response_model=ScanStatus)
def start_scan(db: Session = Depends(get_db)):
    run_id = scan_manager.start_scan(trigger="manual")
    run = db.get(ScrapeRun, run_id)
    return ScanStatus(running=scan_manager.is_running(), run=run)


@router.get("/scan/status", response_model=ScanStatus)
def scan_status(db: Session = Depends(get_db)):
    run = db.query(ScrapeRun).order_by(ScrapeRun.id.desc()).first()
    return ScanStatus(running=scan_manager.is_running(), run=run)


@router.post("/add-by-url", response_model=JobOut)
def add_by_url(payload: AddJobByUrl, db: Session = Depends(get_db)):
    url = payload.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "please paste a full http(s) URL")
    job_dict = fetch_single_job(url)
    if job_dict is None:
        raise HTTPException(
            422, "couldn't read a job from that page — it may block scraping"
        )
    ctx = build_profile_context(db)
    ingest_jobs(db, [job_dict], ctx)  # scores, classifies, dedupes, inserts
    created = db.query(Job).filter(Job.url == url).order_by(Job.id.desc()).first()
    if created is None:
        raise HTTPException(
            422,
            "that job was already in your list, or you removed it earlier — "
            "undo it from Settings to add it again",
        )
    return _mark_new([created], _latest_scan_start(db))[0]


@router.post("/close-stale")
def close_stale(db: Session = Depends(get_db)):
    """Move Sourced jobs that were not seen in the latest completed scan to
    Closed — i.e. postings that have dropped off the boards and are likely no
    longer accepting applications. Reversible: the user can drag them back."""
    latest = (
        db.query(ScrapeRun)
        .filter(ScrapeRun.status == "done")
        .order_by(ScrapeRun.id.desc())
        .first()
    )
    if latest is None or latest.started_at is None:
        return {"closed": 0}
    cutoff = latest.started_at
    stale = (
        db.query(Job)
        .filter(Job.stage == "Sourced", Job.last_seen_at < cutoff)
        .all()
    )
    for job in stale:
        job.stage = "Closed"
    db.commit()
    return {"closed": len(stale)}


@router.get("/runs", response_model=list[ScrapeRunOut])
def list_runs(db: Session = Depends(get_db), limit: int = 20):
    return (
        db.query(ScrapeRun).order_by(ScrapeRun.id.desc()).limit(limit).all()
    )


@router.get("/analytics")
def analytics(db: Session = Depends(get_db)):
    jobs = db.scalars(select(Job)).all()

    applied = [j for j in jobs if j.applied_at]
    responded = [j for j in applied if j.first_reply_at]

    # applications per ISO week (last 8 weeks)
    per_week: dict[str, int] = {}
    for j in applied:
        wk = j.applied_at.strftime("%G-W%V")
        per_week[wk] = per_week.get(wk, 0) + 1
    weeks_sorted = sorted(per_week.items())[-8:]

    # average days to first reply
    gaps = [
        (j.first_reply_at - j.applied_at).total_seconds() / 86400.0
        for j in responded
        if j.first_reply_at and j.applied_at
    ]
    avg_days_to_reply = round(sum(gaps) / len(gaps), 1) if gaps else None

    # source conversion: sourced -> applied per source
    by_source: dict[str, dict] = {}
    for j in jobs:
        s = by_source.setdefault(j.source or "unknown", {"sourced": 0, "applied": 0})
        s["sourced"] += 1
        if j.applied_at:
            s["applied"] += 1
    source_conversion = [
        {
            "source": name,
            "sourced": d["sourced"],
            "applied": d["applied"],
            "rate": round(d["applied"] / d["sourced"], 3) if d["sourced"] else 0,
        }
        for name, d in sorted(by_source.items(), key=lambda kv: -kv[1]["sourced"])
    ]

    stage_counts = {stage: 0 for stage in STAGES}
    for j in jobs:
        stage_counts[j.stage] = stage_counts.get(j.stage, 0) + 1

    return {
        "total_jobs": len(jobs),
        "total_applied": len(applied),
        "response_rate": round(len(responded) / len(applied), 3) if applied else None,
        "avg_days_to_first_reply": avg_days_to_reply,
        "applications_per_week": [{"week": w, "count": c} for w, c in weeks_sorted],
        "source_conversion": source_conversion,
        "stage_counts": stage_counts,
    }


@router.get("/dismissed", response_model=list[DismissedJobOut])
def list_dismissed(db: Session = Depends(get_db)):
    """Jobs the user removed. Scans skip these until they are undone."""
    return (
        db.query(DismissedJob).order_by(DismissedJob.dismissed_at.desc()).all()
    )


@router.delete("/dismissed/{dismissed_id}", status_code=204)
def undismiss(dismissed_id: int, db: Session = Depends(get_db)):
    """Take a job off the blocklist so a future scan can pick it up again. The
    job itself is not restored — it comes back the next time a board lists it."""
    entry = db.get(DismissedJob, dismissed_id)
    if entry is None:
        raise HTTPException(404, "not found")
    db.delete(entry)
    db.commit()


@router.get("", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    stage: str | None = None,
    source: str | None = None,
    min_score: int = 0,
    red_flags: str | None = Query(None, description="'true' = only jobs with red flags"),
    search: str | None = None,
    new_only: bool = False,
    limit: int = 500,
):
    q = select(Job)
    if stage:
        q = q.where(Job.stage == stage)
    if source:
        q = q.where(Job.source == source)
    if min_score:
        q = q.where(Job.score >= min_score)
    q = q.order_by(Job.stage, Job.sort_order, Job.score.desc())
    jobs = db.scalars(q).all()

    cutoff = _latest_scan_start(db)
    _mark_new(jobs, cutoff)

    # filters that are simpler in Python
    if new_only:
        # No completed scan yet means nothing can be new — return nothing rather
        # than silently ignoring the filter.
        jobs = [j for j in jobs if j.is_new] if cutoff else []
    if red_flags == "true":
        jobs = [j for j in jobs if j.red_flags]
    if search:
        s = search.lower()
        jobs = [
            j for j in jobs
            if s in j.title.lower() or s in j.company.lower() or s in j.description.lower()
        ]
    return jobs[:limit]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return _mark_new([job], _latest_scan_start(db))[0]


@router.post("/{job_id}/find-company-site", response_model=CompanySiteOut)
def find_company_site_for_job(job_id: int, db: Session = Depends(get_db)):
    """Best-effort: resolve the company's own careers/application page and save
    it. Returns null when nothing convincing turns up — that is not an error, the
    user can paste the right link by hand."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    url = find_company_site(job.url or "", job.company or "")
    if url:
        job.company_url = url
        db.commit()
    return CompanySiteOut(company_url=url)


@router.patch("/{job_id}", response_model=JobOut)
def patch_job(job_id: int, payload: JobPatch, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")

    if payload.stage is not None:
        if payload.stage not in STAGES:
            raise HTTPException(422, f"stage must be one of {STAGES}")
        _apply_stage_change(job, payload.stage)
    if payload.sort_order is not None:
        job.sort_order = payload.sort_order
    if payload.notes is not None:
        job.notes = payload.notes
    if payload.company_url is not None:
        job.company_url = payload.company_url.strip() or None

    db.commit()
    db.refresh(job)
    return _mark_new([job], _latest_scan_start(db))[0]


def _dismiss(job: Job, db: Session) -> None:
    """Blocklist the posting, then delete it. Order matters: without the
    blocklist entry the next scan would re-ingest it as a brand new job."""
    db.add(
        DismissedJob(
            dedupe_key=job.dedupe_key or dedupe_key(job.title, job.company),
            url=job.url or "",
            title=job.title or "",
            company=job.company or "",
            source=job.source or "",
        )
    )
    db.delete(job)
    db.commit()


@router.post("/{job_id}/dismiss", status_code=204)
def dismiss_job(job_id: int, db: Session = Depends(get_db)):
    """Remove a job you do not qualify for, and keep it from coming back."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    _dismiss(job, db)


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    """Deleting is the same as dismissing: the posting is blocklisted so a
    re-scan does not resurrect it."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    _dismiss(job, db)


def _apply_stage_change(job: Job, new_stage: str) -> None:
    """Set the lifecycle timestamps that analytics depend on when a card moves.
    Timestamps are only set the first time each milestone is reached."""
    now = datetime.utcnow()
    if new_stage == "Applied" and job.applied_at is None:
        job.applied_at = now
    if new_stage in _RESPONDED and job.first_reply_at is None:
        job.first_reply_at = now
        # if the card jumped straight past Applied, backfill applied_at
        if job.applied_at is None:
            job.applied_at = now
    job.stage = new_stage
