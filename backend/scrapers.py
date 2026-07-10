"""Scraper integration.

Reuses the existing job-hunter scrapers in place: it imports the fetch_*
functions from fetch_jobs.py at the repo root rather than reimplementing them,
so that file stays the single source of truth. We only orchestrate here, so we
can run in-process, report progress, and skip the file-writing main().
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable

# Load the scrapers. Prefer a fetch_jobs.py at the parent repo root if one
# exists (so the original stays the single source of truth when developing
# inside the job-hunter repo). Otherwise fall back to the vendored copy that
# ships with the app, so a standalone clone works with no external files.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_parent_scraper = REPO_ROOT / "fetch_jobs.py"

if _parent_scraper.exists():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import fetch_jobs as fj  # noqa: E402
else:
    from . import fetch_jobs_vendored as fj  # noqa: E402

# Query-based sources take a query string; RSS sources take none.
QUERY_SOURCES: list[tuple[str, Callable]] = [
    ("remotive", fj.fetch_remotive),
    ("arbeitnow", fj.fetch_arbeitnow),
    ("himalayas", fj.fetch_himalayas),
    ("remoteok", fj.fetch_remoteok),
    ("linkedin", fj.fetch_linkedin),
    ("hiringcafe", fj.fetch_hiringcafe),
    ("wellfound", fj.fetch_wellfound),
]
RSS_SOURCES: list[tuple[str, Callable]] = [
    ("weworkremotely", fj.fetch_weworkremotely),
    ("remoteco", fj.fetch_remoteco),
]

DEFAULT_QUERIES = fj.QUERIES
# Every source the app knows about, in display order (RSS first).
ALL_SOURCES: list[str] = [name for name, _ in RSS_SOURCES + QUERY_SOURCES]


def build_queries(
    queries: list[str] | None, locations: list[str] | None
) -> list[str]:
    """Effective search terms: the base role queries (a global/remote pass),
    plus one "<role> <city>" variant per user-added location. Empty locations
    keeps the original global-only behavior."""
    base = list(queries or DEFAULT_QUERIES)
    if not locations:
        return base
    effective = list(base)
    seen = set(base)
    for loc in locations:
        loc = loc.strip()
        if not loc:
            continue
        for q in base:
            combined = f"{q} {loc}"
            if combined not in seen:
                seen.add(combined)
                effective.append(combined)
    return effective


def run_scan(
    queries: list[str] | None = None,
    enabled_sources: list[str] | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
    locations: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """Run the enabled sources and return (unique_jobs, per_source_counts).

    Dedupe here is only by URL within this scan; cross-run dedupe against the
    database (including fuzzy title+company) happens in the ingest layer.

    on_progress(source_name, added_now, running_total) is called after each
    source so the caller can stream progress.
    """
    queries = build_queries(queries, locations)
    active = set(enabled_sources) if enabled_sources is not None else set(ALL_SOURCES)
    rss = [(n, f) for n, f in RSS_SOURCES if n in active]
    query_srcs = [(n, f) for n, f in QUERY_SOURCES if n in active]
    seen_urls: set[str] = set()
    jobs: list[dict] = []
    counts: dict[str, int] = {}

    def take(source_name: str, batch: list[dict]) -> None:
        added = 0
        for j in batch or []:
            url = (j.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            jobs.append(j)
            counts[source_name] = counts.get(source_name, 0) + 1
            added += 1
        if on_progress:
            on_progress(source_name, added, len(jobs))

    # RSS sources: one pass each
    for name, fn in rss:
        try:
            take(name, fn())
        except Exception as exc:  # a broken source must not sink the scan
            print(f"[scan] {name} failed: {exc}", file=sys.stderr)
            if on_progress:
                on_progress(name, 0, len(jobs))

    # Query sources: per query
    for q in queries:
        for name, fn in query_srcs:
            try:
                take(name, fn(q))
            except Exception as exc:
                print(f"[scan] {name} '{q}' failed: {exc}", file=sys.stderr)
            time.sleep(0.3)

    return jobs, counts
