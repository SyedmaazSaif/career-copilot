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

from .regional_scrapers import fetch_mustakbil, is_pakistan_location  # noqa: E402

# Remote-only boards. They carry no on-site listings at all, so a location is
# meaningless to them: appending a city to the search term ("product manager
# Islamabad") just matched fewer jobs and multiplied the scan time. They run on
# the base search terms only.
QUERY_SOURCES: list[tuple[str, Callable]] = [
    ("remotive", fj.fetch_remotive),
    ("arbeitnow", fj.fetch_arbeitnow),
    ("himalayas", fj.fetch_himalayas),
    ("remoteok", fj.fetch_remoteok),
    ("hiringcafe", fj.fetch_hiringcafe),
    ("wellfound", fj.fetch_wellfound),
]

# Boards that filter by location natively. Called as fn(query, location), once
# per (query, location) pair. `accepts` gates which locations are worth asking a
# board about — Mustakbil only lists Pakistan, so it is skipped elsewhere.
# (Hiring.cafe's search API would belong here, but it is now auth-gated: POST
# returns 405 and GET 401, so it cannot take a location — or anything else.)
LOCATION_SOURCES: list[tuple[str, Callable, Callable[[str], bool] | None]] = [
    ("linkedin", fj.fetch_linkedin, None),
    ("mustakbil", fetch_mustakbil, is_pakistan_location),
]

RSS_SOURCES: list[tuple[str, Callable]] = [
    ("weworkremotely", fj.fetch_weworkremotely),
    ("remoteco", fj.fetch_remoteco),
]

# The global pass every location-aware board runs in addition to the user's
# cities. LinkedIn's own default for "search everywhere".
GLOBAL_LOCATION = "Worldwide"

DEFAULT_QUERIES = fj.QUERIES
# Every source the app knows about, in display order (RSS first).
ALL_SOURCES: list[str] = [
    name for name, _ in RSS_SOURCES + QUERY_SOURCES
] + [name for name, _, _ in LOCATION_SOURCES]

# The boards that shipped before SearchConfig.known_sources existed. A config
# saved back then has no known_sources, and we must not read that as "the user
# has never been offered any of these" — that would switch a board they had
# deliberately turned off back on. See init_db.
LEGACY_SOURCES: list[str] = [
    "weworkremotely", "remoteco", "remotive", "arbeitnow", "himalayas",
    "remoteok", "linkedin", "hiringcafe", "wellfound",
]


def location_passes(locations: list[str] | None) -> list[str]:
    """The locations to run a location-aware board against: the global pass plus
    whatever the user configured, de-duplicated."""
    passes = [GLOBAL_LOCATION]
    for loc in locations or []:
        loc = loc.strip()
        if loc and loc.lower() not in {p.lower() for p in passes}:
            passes.append(loc)
    return passes


def run_scan(
    queries: list[str] | None = None,
    enabled_sources: list[str] | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
    locations: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """Run the enabled sources and return (unique_jobs, per_source_counts).

    Remote-only boards get the base search terms. Boards that filter by location
    natively (LinkedIn, Mustakbil) get each term once per location: the global
    pass plus every location the user configured.

    Dedupe here is only by URL within this scan; cross-run dedupe against the
    database (including fuzzy title+company) happens in the ingest layer.

    on_progress(source_name, added_now, running_total) is called after each
    source so the caller can stream progress.
    """
    queries = list(queries or DEFAULT_QUERIES)
    passes = location_passes(locations)
    active = set(enabled_sources) if enabled_sources is not None else set(ALL_SOURCES)
    rss = [(n, f) for n, f in RSS_SOURCES if n in active]
    query_srcs = [(n, f) for n, f in QUERY_SOURCES if n in active]
    loc_srcs = [(n, f, a) for n, f, a in LOCATION_SOURCES if n in active]
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

    # Query sources: per query, no location (they are remote-only boards)
    for q in queries:
        for name, fn in query_srcs:
            try:
                take(name, fn(q))
            except Exception as exc:
                print(f"[scan] {name} '{q}' failed: {exc}", file=sys.stderr)
            time.sleep(0.3)

        # Location-aware sources: per query, per location the board covers
        for name, fn, accepts in loc_srcs:
            for loc in passes:
                if accepts is not None and not accepts(loc):
                    continue
                try:
                    take(name, fn(q, loc))
                except Exception as exc:
                    print(
                        f"[scan] {name} '{q}' @ '{loc}' failed: {exc}",
                        file=sys.stderr,
                    )
                time.sleep(0.3)

    return jobs, counts
