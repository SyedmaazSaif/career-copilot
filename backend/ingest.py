"""Ingest scraped jobs into the database: filter, dedupe, score, upsert.

Dedupe is layered, and the layering matters. Roughly one posting in three is a
ghost job and the same real job is cross-posted to several boards under
slightly different titles, so matching too loosely hides real jobs and matching
too tightly fills the list with the same role five times.

1. exact URL, with tracking parameters stripped
2. exact normalised title+company key
3. fuzzy title+company -- but only when the locations are compatible

Step 3 is where the old version was wrong. At a 0.92 ratio, "Sales Manager
(Dubai)" and "Sales Manager (Abu Dhabi)" are the same job, and the same
comparison guarded the dismissed-job blocklist, so dismissing one city's role
silently suppressed another city's. Locations now have to be compatible before
a fuzzy match counts.

See docs/MATCHING.md for the evidence behind these choices.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import taxonomy
from .ats import is_ats_url
from .matching import score_job
from .models import DismissedJob, Job, SearchConfig
from .salary import parse_salary
from .scoring import extract_requirements
from .textutil import clean_description

_COMPANY_SUFFIX = re.compile(
    r"\b(inc|inc\.|llc|ltd|ltd\.|limited|gmbh|corp|corporation|co|plc|bv|ag)\b",
    re.I,
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
FUZZY_THRESHOLD = 0.92

# Board decoration that says nothing about which job this is. Stripped before
# keying so "Product Designer [Remote]" and "Product Designer" collapse.
_TITLE_NOISE = re.compile(
    r"\((?:100%\s*)?remote[^)]*\)|\[[^\]]*remote[^\]]*\]|\b(?:100%\s*)?remote\b|"
    r"\bwork from home\b|\bwfh\b|\bhiring now\b|\burgent\b|\bnew\b\s*$",
    re.I,
)

# Analytics and campaign parameters. Two links to the same posting differ only
# by these, so they must not make it look like two postings.
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gh_src", "gh_jid", "ref", "referer", "referrer", "source", "src",
    "trk", "trackingid", "position", "pagenum", "origin", "fbclid", "gclid",
}


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = _COMPANY_SUFFIX.sub(" ", s)
    s = _NON_ALNUM.sub(" ", s)
    return " ".join(s.split())


def clean_title(title: str) -> str:
    """Strip board decoration, keeping the actual role name."""
    cleaned = _TITLE_NOISE.sub(" ", title or "")
    cleaned = re.sub(r"[\s\-–—|,]+$", "", " ".join(cleaned.split()))
    return cleaned.strip() or (title or "").strip()


def dedupe_key(title: str, company: str) -> str:
    return f"{_norm(clean_title(title))}::{_norm(company)}"


def norm_url(url: str) -> str:
    """Loose URL identity: lowercase, no trailing slash, no tracking parameters."""
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        kept = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in _TRACKING_PARAMS
        ]
        raw = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(kept), "")
        )
    except ValueError:
        pass  # not a parseable URL; fall back to the raw string
    return raw.rstrip("/").lower()


def _location_token_set(location: str) -> set[str]:
    """Place words worth comparing. Words that appear in every location string
    are useless for telling two postings apart."""
    generic = {
        "remote", "hybrid", "onsite", "on", "site", "anywhere", "worldwide",
        "global", "usa", "us", "uk", "eu", "europe", "america", "united",
        "states", "kingdom", "office", "area", "region", "metro", "greater",
    }
    return {
        w for w in _NON_ALNUM.sub(" ", (location or "").lower()).split()
        if len(w) > 2 and w not in generic
    }


def locations_compatible(a: str, b: str) -> bool:
    """Whether two postings could be the same job as far as place is concerned.

    If either side names no specific place, there is nothing to contradict, so
    they stay compatible. If both name places and none of them overlap, these
    are two different jobs however similar their titles read.
    """
    ta, tb = _location_token_set(a), _location_token_set(b)
    if not ta or not tb:
        return True
    return bool(ta & tb)


def _split_company(title: str, company: str) -> tuple[str, str]:
    """Some boards (e.g. We Work Remotely) embed the company in the title as
    'Company: Role'. If company is blank and the title carries that shape, split
    it out so cards and dedupe have a real company."""
    if company or ": " not in title:
        return title, company
    head, _, rest = title.partition(": ")
    if rest and 1 <= len(head.split()) <= 5 and len(head) <= 40:
        return rest.strip(), head.strip()
    return title, company


# ---------------------------------------------------------------------------
# Posting age
# ---------------------------------------------------------------------------

_REL_AGE = re.compile(
    r"(\d+)\+?\s*(minute|min|hour|hr|day|week|month)s?\s*(?:ago)?", re.I
)
_UNIT_DAYS = {
    "minute": 0, "min": 0, "hour": 0, "hr": 0,
    "day": 1, "week": 7, "month": 30,
}


def parse_posted(posted: str, now: datetime | None = None) -> datetime | None:
    """Turn a board's free-text `posted` into a date, best effort.

    Boards write this every way imaginable -- "3 days ago", "2026-09-01",
    "Posted 2 weeks ago", "Just posted". Age is the single strongest honest
    signal that a posting is a ghost, so it is worth the parsing; anything
    unrecognised returns None rather than a guess.
    """
    # `posted` comes straight from whatever a board's API returns. Every
    # scraper is supposed to hand back a string, but a board changing its
    # field's type (Arbeitnow once sent a raw Unix timestamp) must not be
    # able to crash the whole ingest -- coerce defensively rather than trust it.
    text = (str(posted) if posted else "").strip()
    if not text:
        return None
    now = now or datetime.utcnow()

    low = text.lower()
    if any(k in low for k in ("just posted", "today", "new", "just now")):
        return now
    if "yesterday" in low:
        return now - timedelta(days=1)

    match = _REL_AGE.search(low)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        return now - timedelta(days=amount * _UNIT_DAYS.get(unit, 0))

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text[:11].strip(), fmt)
        except ValueError:
            continue
    # ISO timestamps from JSON feeds
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


def ingest_jobs(db: Session, scraped: list[dict], profile: dict) -> tuple[int, int]:
    """Insert new jobs; refresh the ones already known.

    Returns (new_count, seen_total).
    """
    existing = db.scalars(select(Job)).all()
    by_url = {norm_url(j.url): j for j in existing if j.url}
    keys = {j.dedupe_key: j for j in existing if j.dedupe_key}
    key_list = list(keys.keys())
    now = datetime.utcnow()

    config = db.get(SearchConfig, 1)
    excluded = set(config.excluded_categories or []) if config else set()
    blocked_companies = {
        c.strip().lower() for c in (config.company_block_list or []) if c.strip()
    } if config else set()
    exclusion_keywords = [
        k.strip().lower() for k in (config.exclusion_keywords or []) if k.strip()
    ] if config else []
    excluded_industries = [
        i.strip().lower() for i in (config.excluded_industries or []) if i.strip()
    ] if config else []

    # Jobs the user removed. Their rows are gone, so without this they would be
    # re-ingested as brand new on the next scan.
    dismissed = db.scalars(select(DismissedJob)).all()
    dismissed_urls = {norm_url(d.url) for d in dismissed if d.url}
    dismissed_keys = {d.dedupe_key for d in dismissed if d.dedupe_key}

    new_count = 0
    for raw in scraped:
        url = (raw.get("url") or "").strip()
        title = (raw.get("title") or "").strip()
        company = (raw.get("company") or "").strip()
        if not title or not url:
            continue
        title, company = _split_company(title, company)
        title = clean_title(title)
        location = raw.get("location", "") or "Remote"

        if company.lower() in blocked_companies:
            continue

        key = dedupe_key(title, company)
        nurl = norm_url(url)

        # The user removed this posting -- never bring it back. Only exact
        # matches here: a fuzzy blocklist suppresses jobs the user never saw.
        if nurl in dismissed_urls or key in dismissed_keys:
            continue

        # Category is decided before anything expensive happens, so an excluded
        # category costs nothing: it is never scored and never stored.
        description = clean_description(raw.get("description", "") or "")
        category = taxonomy.classify(title, description)
        if category in excluded:
            continue

        # User-set exclusion keywords / industries: drop and never store.
        blob = f"{title} {description} {' '.join(raw.get('tags') or [])}".lower()
        if any(k in blob for k in exclusion_keywords):
            continue
        if any(k in blob for k in excluded_industries):
            continue

        match = by_url.get(nurl) or keys.get(key)
        if match is None:
            for k in key_list:
                if SequenceMatcher(None, key, k).ratio() >= FUZZY_THRESHOLD:
                    candidate = keys[k]
                    if locations_compatible(location, candidate.location or ""):
                        match = candidate
                        break

        if match is not None:
            # Keep the best version of a cross-posted job: prefer the direct
            # company (ATS) link over an aggregator link.
            if is_ats_url(url) and not is_ats_url(match.url or ""):
                match.url = url
                match.source = raw.get("source", "")
            # Seen again. Reset the miss counter, and if a previous scan had
            # retired it, put it back: a posting that reappears was paused or
            # hit a listing window, not closed.
            match.last_seen_at = now
            match.missed_scans = 0
            match.sightings = (match.sightings or 1) + 1
            if match.stage == "Closed" and match.closed_reason.startswith("not seen"):
                match.stage = "Sourced"
                match.closed_at = None
                match.closed_reason = ""
            continue

        # New job -- score and insert.
        result = score_job(
            {
                "title": title,
                "description": description,
                "location": location,
                "tags": raw.get("tags", []) or [],
            },
            profile,
        )
        salary = parse_salary(f"{description} {title}")
        job = Job(
            source=raw.get("source", ""),
            title=title,
            company=company,
            location=location,
            url=url,
            description=description,
            requirements=extract_requirements(description),
            posted=raw.get("posted", "") or "",
            posted_at=parse_posted(raw.get("posted", "") or "", now),
            tags=raw.get("tags", []) or [],
            category=category,
            work_type=result["work_type"],
            employment_type=result["employment_type"],
            score=result["score"],
            score_reason=result["reason"],
            red_flags=result["red_flags"],
            explanations=result["explanations"],
            score_version=result["score_version"],
            salary_min=salary["min"] if salary else None,
            salary_max=salary["max"] if salary else None,
            salary_text=salary["text"] if salary else "",
            salary_parsed=True,
            dedupe_key=key,
            stage="Sourced",
            first_scanned_at=now,
            last_seen_at=now,
            sightings=1,
            missed_scans=0,
        )
        db.add(job)
        # keep the in-memory indexes fresh so this scan is internally deduped
        by_url[nurl] = job
        keys[key] = job
        key_list.append(key)
        new_count += 1

    db.commit()
    return new_count, len(scraped)
