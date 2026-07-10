"""Runs scans in a background thread so the API stays responsive.

Only one scan runs at a time. Progress is written to the ScrapeRun row as each
source reports in, so the frontend can poll and show a live source breakdown.
"""
from __future__ import annotations

import threading
from datetime import datetime

from .custom_scrapers import run_custom_sources
from .db import SessionLocal
from .ingest import ingest_jobs
from .models import CustomSource, ScrapeRun, SearchConfig
from .scoring import build_profile_context
from .scrapers import run_scan

_lock = threading.Lock()
_thread: threading.Thread | None = None


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()


def start_scan(trigger: str = "manual") -> int:
    """Start a scan if none is running. Returns the ScrapeRun id (new or active)."""
    global _thread
    with _lock:
        if is_running():
            # return the id of the run in progress
            with SessionLocal() as db:
                active = (
                    db.query(ScrapeRun)
                    .filter(ScrapeRun.status == "running")
                    .order_by(ScrapeRun.id.desc())
                    .first()
                )
                if active:
                    return active.id
        # create the run row up front so status polling has something to read
        with SessionLocal() as db:
            run = ScrapeRun(trigger=trigger, status="running")
            db.add(run)
            db.commit()
            run_id = run.id

        _thread = threading.Thread(target=_run, args=(run_id,), daemon=True)
        _thread.start()
        return run_id


def _run(run_id: int) -> None:
    try:
        with SessionLocal() as db:
            ctx = build_profile_context(db)
            config = db.get(SearchConfig, 1)
            queries = list(config.queries) if config and config.queries else None
            enabled = (
                list(config.enabled_sources)
                if config and config.enabled_sources is not None
                else None
            )
            locations = (
                list(config.locations) if config and config.locations else None
            )

        def on_progress(source: str, added: int, total: int) -> None:
            with SessionLocal() as db:
                run = db.get(ScrapeRun, run_id)
                if run is None:
                    return
                counts = dict(run.source_counts or {})
                counts[source] = counts.get(source, 0) + added
                run.source_counts = counts
                run.total_found = total
                db.commit()

        jobs, _counts = run_scan(
            queries=queries,
            enabled_sources=enabled,
            on_progress=on_progress,
            locations=locations,
        )

        # User-added custom sources (RSS / Greenhouse / Lever / URL)
        with SessionLocal() as db:
            custom = db.query(CustomSource).filter(CustomSource.enabled == True).all()  # noqa: E712
        if custom:
            custom_jobs, _cc = run_custom_sources(custom, on_progress=on_progress)
            jobs.extend(custom_jobs)

        with SessionLocal() as db:
            new_count, seen_total = ingest_jobs(db, jobs, ctx)
            run = db.get(ScrapeRun, run_id)
            run.total_found = seen_total
            run.total_new = new_count
            run.status = "done"
            run.finished_at = datetime.utcnow()
            db.commit()
    except Exception as exc:  # never leave a run stuck as "running"
        with SessionLocal() as db:
            run = db.get(ScrapeRun, run_id)
            if run is not None:
                run.status = "error"
                run.error = str(exc)[:2000]
                run.finished_at = datetime.utcnow()
                db.commit()
