"""Run the direct-link resolver over already-saved jobs (backfill).

Usage:
    backend/.venv/bin/python -m backend.resolve_backfill [--limit N] [--delay S]

Prints a summary (how many resolved as direct_job / careers_page / original,
and by which method) and saves the results into the database. It reads the live
database and applies the same column migration the app applies on startup.
"""
from __future__ import annotations

import argparse

from .db import SessionLocal, init_db
from .resolver import resolve_due_jobs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill direct links for already-saved jobs."
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="max jobs to resolve (default: every job that still needs one)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="seconds to wait between jobs (default: 0.5)",
    )
    args = parser.parse_args(argv)

    init_db()  # ensures the new columns exist, then backfills legacy company_url

    with SessionLocal() as db:
        stats = resolve_due_jobs(db, limit=args.limit, delay=args.delay)

    by_method = stats.pop("by_method", {})
    total = sum(v for v in stats.values() if isinstance(v, int))
    print("\nDirect-link backfill complete.")
    print(f"  jobs attempted: {total}")
    for key in ("direct_job", "careers_page", "original", "failed"):
        print(f"  {key:14s} {stats.get(key, 0)}")
    print("  by method:")
    for method in sorted(by_method):
        print(f"    {method:14s} {by_method[method]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
