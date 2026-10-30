"""Runs scans in a background thread so the API stays responsive.

Only one scan runs at a time. Progress is written to the ScrapeRun row as each
source reports in, so the frontend can poll and show a live source breakdown.

After every scan the stale sweep runs, which is what stops the list filling up
with postings that closed months ago. It used to be a button nobody pressed.
"""
from __future__ import annotations

import threading
from datetime import datetime

from .company_registry import (
    add_company,
    auto_add_from_jobs,
    drop_after_failures,
    fetch_registry_jobs,
)
from .custom_scrapers import run_custom_sources
from .web_discovery import discover_boards
from .db import SessionLocal
from .ingest import ingest_jobs
from .matching import build_profile, derive_queries
from .models import CustomSource, Job, ScrapeRun, SearchConfig
from .scrapers import run_scan

_lock = threading.Lock()
_thread: threading.Thread | None = None

# How many consecutive scans a posting must be absent from before it is
# retired. Two, not one: a posting disappears for reasons that have nothing to
# do with the job being filled -- the employer paused it, a free listing hit
# its 30-day window, a sponsored budget ran out -- and boards themselves fail
# often enough that a single absence means very little. Postings routinely
# reappear days later, so a miss is evidence, not proof.
MISSES_BEFORE_CLOSE = 2

CLOSED_REASON = "not seen in the last two scans"


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()


def start_scan(trigger: str = "manual") -> int:
    """Start a scan if none is running. Returns the ScrapeRun id (new or active)."""
    global _thread
    with _lock:
        if is_running():
            with SessionLocal() as db:
                active = (
                    db.query(ScrapeRun)
                    .filter(ScrapeRun.status == "running")
                    .order_by(ScrapeRun.id.desc())
                    .first()
                )
                if active:
                    return active.id
        with SessionLocal() as db:
            run = ScrapeRun(trigger=trigger, status="running")
            db.add(run)
            db.commit()
            run_id = run.id

        _thread = threading.Thread(target=_run, args=(run_id,), daemon=True)
        _thread.start()
        return run_id


def sweep_stale(
    db,
    healthy_sources: set[str],
    started_at: datetime,
    productive_sources: set[str] | None = None,
) -> int:
    """Retire postings that have now missed enough scans, and return how many.

    Two guards, each there because without it the sweep closes live jobs:

    1. Only sources that responded this run are considered. If LinkedIn was
       rate-limited, every LinkedIn job looks like it vanished.
    2. Only sources that actually RETURNED jobs this run count a miss. A board
       that answers with an empty list -- because its search endpoint changed,
       or the query matched nothing that day -- is not evidence that everything
       it ever listed has closed. This is also what stops a stale run record
       from retiring an entire long-idle list: with no productive source there
       is nothing to count a miss against.

    Together they mean a miss is only recorded when the job's own board was
    scanned, answered, returned postings, and this one was not among them.

    Closed jobs are not deleted and not hidden. They move to the Closed column
    with the reason and date recorded, so the user can see what happened and
    put anything back. `reopen_auto_closed` undoes the lot if it gets it wrong.
    """
    considered = healthy_sources
    if productive_sources is not None:
        considered = healthy_sources & productive_sources
    if not considered:
        return 0

    stale = (
        db.query(Job)
        .filter(
            Job.stage == "Sourced",
            Job.last_seen_at < started_at,
            Job.source.in_(considered),
        )
        .all()
    )

    closed = 0
    now = datetime.utcnow()
    for job in stale:
        job.missed_scans = (job.missed_scans or 0) + 1
        if job.missed_scans >= MISSES_BEFORE_CLOSE:
            job.stage = "Closed"
            job.closed_at = now
            job.closed_reason = CLOSED_REASON
            closed += 1
    db.commit()
    return closed


def reopen_auto_closed(db) -> int:
    """Put back everything the sweep closed, and reset the miss counters.

    The escape hatch for when the sweep got it wrong -- a run of broken boards,
    or an upgrade that made a long-idle list look abandoned. Only touches jobs
    the app closed by itself; anything the user moved to Closed by hand stays
    where they put it.
    """
    auto = (
        db.query(Job)
        .filter(Job.stage == "Closed", Job.closed_reason == CLOSED_REASON)
        .all()
    )
    for job in auto:
        job.stage = "Sourced"
        job.closed_at = None
        job.closed_reason = ""
        job.missed_scans = 0
    db.commit()
    return len(auto)


def _run(run_id: int) -> None:
    try:
        with SessionLocal() as db:
            profile = build_profile(db)
            config = db.get(SearchConfig, 1)
            queries = (
                list(config.queries)
                if config and config.queries
                else derive_queries(profile)
            )
            enabled = (
                list(config.enabled_sources)
                if config and config.enabled_sources is not None
                else None
            )
            locations = list(config.locations) if config and config.locations else None
            run = db.get(ScrapeRun, run_id)
            started_at = run.started_at if run else datetime.utcnow()

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

        jobs, _counts, health = run_scan(
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

        # Target company boards from the registry (user-added + auto-discovered).
        with SessionLocal() as db:
            registry_jobs = fetch_registry_jobs(db, on_progress=on_progress)
        if registry_jobs:
            jobs.extend(registry_jobs)

        # A source counts as working if at least one of its calls came back
        # without raising. Zero results from a working board is a real signal
        # (nothing matched); zero results from a broken one is not.
        healthy = {name for name, h in health.items() if h.get("ok", 0) > 0}
        # A board that answered but returned nothing is not evidence that its
        # jobs closed -- an endpoint change looks exactly like an empty result.
        productive = {name for name, n in _counts.items() if n > 0}

        # Best-effort ATS board discovery via web search (capped; never fatal).
        discovered = discover_boards(queries)
        if discovered:
            with SessionLocal() as db:
                for kind, slug in discovered:
                    add_company(db, slug, kind, slug, auto_added=True)

        with SessionLocal() as db:
            new_count, seen_total = ingest_jobs(db, jobs, profile)
            closed = sweep_stale(db, healthy, started_at, productive)
            added_companies = auto_add_from_jobs(db, jobs)
            dropped_companies = drop_after_failures(db)
            if added_companies:
                print(f"[registry] auto-added {added_companies} company board(s)")
            if dropped_companies:
                print(f"[registry] dropped {dropped_companies} failing board(s)")
            run = db.get(ScrapeRun, run_id)
            run.total_found = seen_total
            run.total_new = new_count
            run.total_closed = closed
            run.status = "done"
            run.finished_at = datetime.utcnow()
            db.commit()
    except Exception as exc:  # never leave a run stuck as "running"
        import traceback
        traceback.print_exc()
        with SessionLocal() as db:
            run = db.get(ScrapeRun, run_id)
            if run is not None:
                run.status = "error"
                run.error = str(exc)[:2000]
                run.finished_at = datetime.utcnow()
                db.commit()
