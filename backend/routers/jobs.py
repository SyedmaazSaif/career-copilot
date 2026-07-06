"""Jobs + CRM API: scan, list/filter, pipeline moves, analytics, run history."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import scan_manager
from ..custom_scrapers import fetch_single_job
from ..db import get_db
from ..ingest import ingest_jobs
from ..models import STAGES, Job, ScrapeRun
from ..schemas import AddJobByUrl, JobOut, JobPatch, ScanStatus, ScrapeRunOut
from ..scoring import build_profile_context

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Stages that count as "the application got a response".
_RESPONDED = {"Screening", "Interview", "Offer"}


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
        raise HTTPException(500, "job was fetched but could not be saved")
    return created


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


@router.get("", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    stage: str | None = None,
    source: str | None = None,
    min_score: int = 0,
    red_flags: str | None = Query(None, description="'true' = only jobs with red flags"),
    search: str | None = None,
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

    # filters that are simpler in Python
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
    return job


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

    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    db.delete(job)
    db.commit()


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
