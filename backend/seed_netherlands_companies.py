"""Seed the 18 Netherlands companies into the target-companies registry.

Idempotent: re-running updates names/enabled flags and never duplicates rows
(dedupe is on (ats, slug)). Companies whose careers page has no public,
machine-readable job board are added disabled with "(needs source)" in the name,
so they are visible in Settings but never scanned.

Usage:
    backend/.venv/bin/python -m backend.seed_netherlands_companies
"""
from __future__ import annotations

from sqlalchemy import select

from .company_registry import add_company
from .db import SessionLocal, init_db
from .models import Company

# (display name, ATS kind, board slug or feed URL)
COMPANIES = [
    ("Optiver", "optiver", "optiver"),
    ("Flow Traders", "greenhouse", "flowtraders"),
    ("Maven Securities", "ashby", "maven"),
    ("BlockTech", "ashby", "blocktech"),
    ("Leaseweb", "teamtailor", "leaseweb"),
    ("Bitvavo", "ashby", "bitvavo"),
    ("Stream", "ashby", "stream"),
    ("Plumerai", "ashby", "plumerai"),
    ("GreenFlux", "recruitee", "greenflux"),
    ("Gerimedica", "recruitee", "gerimedica"),
    ("OLYX", "recruitee", "olyx"),
    ("Flexport", "greenhouse", "flexport"),
    ("A2G Consulting", "rss", "https://a2gtechnologies.com/jobs/feed/"),
    ("Wypoon Technologies", "lever", "wypoon"),
    ("Riverflex", "recruitee", "riverflex"),
    ("Rightangled", "workable", "rightangled"),
]

# Companies with no readable public source yet (not silently skipped).
NEEDS_SOURCE = [
    ("Secfi (needs source)", "Homerun JS embed; account slug not publicly discoverable"),
    ("AMOLF (needs source)", "custom WordPress site; no public vacancy feed/API"),
]


def main() -> int:
    init_db()
    with SessionLocal() as db:
        for name, ats, slug in COMPANIES:
            c, created = add_company(db, name, ats, slug, auto_added=False)
            if c is None:
                print(f"FAILED  {name} ({ats}, {slug})")
                continue
            c.enabled = True
            c.name = name
            db.commit()
            print(f"{'added  ' if created else 'exists '} {name:22s} {ats:11s} {slug}")

        for name, reason in NEEDS_SOURCE:
            c = db.scalars(select(Company).where(Company.name == name)).first()
            if c is None:
                db.add(Company(name=name, ats="", slug="", enabled=False, auto_added=False))
            else:
                c.ats = ""
                c.slug = ""
                c.enabled = False
            db.commit()
            print(f"needs-source {name}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
