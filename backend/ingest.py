"""Ingest scraped jobs into the database: dedupe, score, and upsert.

Dedupe is layered:
1. exact URL match (same posting seen again),
2. exact normalized title+company key,
3. fuzzy title+company (difflib ratio) to catch the same role cross-posted to
   several boards with tiny wording differences.
"""
from __future__ import annotations

import re
from datetime import datetime
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DismissedJob, Job
from .salary import parse_salary
from .scoring import extract_requirements, score_job
from .textutil import clean_description

_COMPANY_SUFFIX = re.compile(
    r"\b(inc|inc\.|llc|ltd|ltd\.|limited|gmbh|corp|corporation|co|plc|bv|ag)\b",
    re.I,
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
FUZZY_THRESHOLD = 0.92


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = _COMPANY_SUFFIX.sub(" ", s)
    s = _NON_ALNUM.sub(" ", s)
    return " ".join(s.split())


def dedupe_key(title: str, company: str) -> str:
    return f"{_norm(title)}::{_norm(company)}"


def norm_url(url: str) -> str:
    """Loose URL identity: ignores case and a trailing slash. Used to match a
    scraped posting against the dismissed blocklist."""
    return (url or "").strip().rstrip("/").lower()


def _split_company(title: str, company: str) -> tuple[str, str]:
    """Some boards (e.g. We Work Remotely) embed the company in the title as
    'Company: Role'. If company is blank and the title carries that shape, split
    it out so cards and dedupe have a real company."""
    if company or ": " not in title:
        return title, company
    head, _, rest = title.partition(": ")
    # only treat as company if the head looks like a name, not a sentence
    if rest and 1 <= len(head.split()) <= 5 and len(head) <= 40:
        return rest.strip(), head.strip()
    return title, company


def ingest_jobs(db: Session, scraped: list[dict], ctx: dict) -> tuple[int, int]:
    """Insert new jobs; refresh last_seen_at for ones already known.

    Returns (new_count, seen_total).
    """
    existing = db.scalars(select(Job)).all()
    urls = {j.url for j in existing if j.url}
    keys = {j.dedupe_key: j for j in existing if j.dedupe_key}
    key_list = list(keys.keys())
    now = datetime.utcnow()

    # Jobs the user removed. Their rows are gone, so without this they would be
    # re-ingested as brand new on the next scan.
    dismissed = db.scalars(select(DismissedJob)).all()
    dismissed_urls = {norm_url(d.url) for d in dismissed if d.url}
    dismissed_keys = {d.dedupe_key for d in dismissed if d.dedupe_key}
    dismissed_key_list = list(dismissed_keys)

    new_count = 0
    for raw in scraped:
        url = (raw.get("url") or "").strip()
        title = (raw.get("title") or "").strip()
        company = (raw.get("company") or "").strip()
        if not title or not url:
            continue
        title, company = _split_company(title, company)

        key = dedupe_key(title, company)

        # 0: the user removed this posting — never bring it back
        if norm_url(url) in dismissed_urls or key in dismissed_keys:
            continue
        if any(
            SequenceMatcher(None, key, k).ratio() >= FUZZY_THRESHOLD
            for k in dismissed_key_list
        ):
            continue

        # 1 + 2: exact URL or exact key already known
        match = None
        if url in urls:
            match = next((j for j in existing if j.url == url), None)
        elif key in keys:
            match = keys[key]
        else:
            # 3: fuzzy title+company against known keys
            for k in key_list:
                if SequenceMatcher(None, key, k).ratio() >= FUZZY_THRESHOLD:
                    match = keys[k]
                    break

        if match is not None:
            match.last_seen_at = now
            continue

        # New job — score and insert
        score, reason, red_flags, work_type, employment_type = score_job(raw, ctx)
        description = clean_description(raw.get("description", "") or "")
        salary = parse_salary(f"{description} {title}")
        job = Job(
            source=raw.get("source", ""),
            title=title,
            company=company,
            location=raw.get("location", "") or "Remote",
            url=url,
            description=description,
            requirements=extract_requirements(description),
            posted=raw.get("posted", "") or "",
            tags=raw.get("tags", []) or [],
            work_type=work_type,
            employment_type=employment_type,
            score=score,
            score_reason=reason,
            red_flags=red_flags,
            salary_min=salary["min"] if salary else None,
            salary_max=salary["max"] if salary else None,
            salary_text=salary["text"] if salary else "",
            salary_parsed=True,
            dedupe_key=key,
            stage="Sourced",
            first_scanned_at=now,
            last_seen_at=now,
        )
        db.add(job)
        # keep in-memory sets fresh so this scan is internally deduped too
        urls.add(url)
        keys[key] = job
        key_list.append(key)
        new_count += 1

    db.commit()
    return new_count, len(scraped)
