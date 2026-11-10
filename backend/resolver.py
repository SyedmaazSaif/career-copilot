"""Direct-link resolver.

For each job, find the job's original posting on the hiring company's own site
or its applicant-tracking system (ATS), and save it. This only ever looks at
publicly available postings — it never logs in, bypasses, or scrapes behind a
paywall.

Resolution order (stop at the first success):
  A) source fields — the stored URL already points off the aggregator
  B) follow redirects — the listing's final destination is the company's site
  C) ATS lookup — guess the company's board slug, match the exact job
  D) web search — "<company>" "<title>" careers via free search engines
  E) careers page fallback — the company's own careers/jobs page
  F) nothing — leave direct_url empty, link_type "original"

Every network call is polite (short timeouts, the app's honest user-agent) and
every failure returns a normal "not found" rather than raising, so a resolver
problem can never stop a scan.
"""
from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .ats import fetch_board
from .blocklist import host_of, is_blocked, is_direct_candidate
from .company_registry import add_company
from .company_site import (
    HEADERS,
    _bing_results,
    _ddg_results,
    _is_ats,
    _root,
)
from .models import Company, Job

# link_type values
DIRECT_JOB = "direct_job"
CAREERS_PAGE = "careers_page"
ORIGINAL = "original"

# resolved_via values
VIA_SOURCE_FIELD = "source_field"
VIA_REDIRECT = "redirect"
VIA_ATS = "ats"
VIA_SEARCH = "search"
VIA_CAREERS_PAGE = "careers_page"
VIA_NONE = "none"

# How many jobs a single scan resolves (new jobs accumulate daily; the backfill
# command handles the backlog). Keeping this small keeps scans fast and polite.
DEFAULT_SCAN_RESOLVE_LIMIT = 10

# "original" results are retried no more than once per day.
RETRY_AFTER = timedelta(days=1)

# Delay between one job's resolve and the next, so no site sees a burst.
RESOLVE_DELAY = 0.5

# ATS kinds whose public board endpoints were verified live (see ats.py).
# SmartRecruiters is robots-blocked and Recruitee is unverified, so they are
# deliberately not probed here.
_ATS_PROBE_KINDS = ("greenhouse", "lever", "ashby", "workable")

_COMPANY_SUFFIX = re.compile(
    r"\b(inc|ltd|llc|llp|lp|gmbh|corp|corporation|co|plc|ag|bv|limited|company)\b",
    re.I,
)
# Words that rarely appear in a board slug and only create misses.
_NAME_NOISE = {
    "the", "group", "holdings", "technologies", "technology", "labs",
    "solutions", "services",
}

# ATS domains whose public job boards host the employer's own posting. Used to
# decide which search results are trustworthy (an employer's posting can live on
# any of these, independent of the company's own domain name).
_SEARCH_ATS_HOSTS = (
    "greenhouse.io", "lever.co", "workable.com", "ashbyhq.com",
    "bamboohr.com", "smartrecruiters.com", "recruitee.com",
    "myworkdayjobs.com", "teamtailor.com", "jobvite.com", "icims.com",
    "rippling.com", "pinpointhq.com", "personio.com",
)

_CLOSED_PHRASES = (
    "position has been filled",
    "this job is no longer",
    "job is no longer available",
    "job has been closed",
    "position has been closed",
    "no longer accepting",
    "this posting has expired",
    "posting has been filled",
    "this role is no longer",
    "job closed",
)


@dataclass
class ResolveResult:
    direct_url: str | None = None
    link_type: str = ORIGINAL
    resolved_via: str = VIA_NONE


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable without the network)
# ---------------------------------------------------------------------------


def _name_words(company: str) -> list[str]:
    name = _COMPANY_SUFFIX.sub(" ", (company or "").lower())
    return [w for w in re.findall(r"[a-z0-9]+", name) if w not in _NAME_NOISE]


def _norm_name(company: str) -> str:
    return "".join(_name_words(company))


def _is_search_ats(url: str) -> bool:
    """True when a search result is on a known ATS job-board domain — these host
    the employer's own posting, whatever the employer's own domain is."""
    host = host_of(url)
    return any(host == h or host.endswith("." + h) for h in _SEARCH_ATS_HOSTS)


def _domain_relevant(company: str, url: str) -> bool:
    """Does the company's name appear in the result's hostname? A mirror/board
    site that embeds the company in its URL path is not the company's own site."""
    host = host_of(url)
    words = [
        w for w in re.findall(r"[a-z0-9]+", (company or "").lower())
        if len(w) >= 3 and w not in _NAME_NOISE
    ]
    if not words:
        return False
    compact = "".join(words)
    if compact in host:
        return True
    # Any distinctive word (5+ chars) in the host is a strong signal — this
    # catches abbreviations like cfchildren.org for "Committee for Children".
    if any(w in host for w in words if len(w) >= 5):
        return True
    longest = max(words, key=len)
    return longest in host


def build_slugs(company: str) -> list[str]:
    """Candidate board slugs from a company name: lowercase, no legal suffixes,
    joined with hyphens (plus the compact no-hyphen form and the leading word)."""
    words = _name_words(company)
    if not words:
        return []
    slugs: list[str] = []
    for candidate in ("-".join(words), "".join(words)):
        if candidate and candidate not in slugs:
            slugs.append(candidate)
    if len(words) > 1 and words[0] not in slugs:
        slugs.append(words[0])
    return slugs


def _clean(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (title or "").lower()))


def title_matches(candidate: str, target: str, threshold: float = 0.8) -> bool:
    """Loose title match: identical, contained, or strongly similar."""
    a, b = _clean(candidate), _clean(target)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


_GENERIC_LOC = {
    "remote", "hybrid", "onsite", "on", "site", "anywhere", "worldwide",
    "global", "usa", "us", "uk", "eu", "europe", "america", "united",
    "states", "kingdom", "office", "area", "region", "metro", "greater",
}


def _location_tokens(location: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z0-9]+", (location or "").lower())
        if len(w) > 2 and w not in _GENERIC_LOC
    }


def locations_compatible(a: str, b: str) -> bool:
    """Two postings could be the same job as far as place is concerned."""
    ta, tb = _location_tokens(a), _location_tokens(b)
    if not ta or not tb:
        return True
    return bool(ta & tb)


# ---------------------------------------------------------------------------
# Verification (Step 3)
# ---------------------------------------------------------------------------


def _page_text(html: str | None) -> str:
    try:
        return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
    except Exception:
        return html or ""


def _looks_closed(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in _CLOSED_PHRASES)


def _contains_title(text: str, title: str) -> bool:
    tokens = [t for t in re.findall(r"[a-z0-9]+", (title or "").lower()) if len(t) > 2]
    if not tokens:
        return True  # nothing to check
    blob = text.lower()
    hits = sum(1 for t in tokens if t in blob)
    return hits / len(tokens) >= 0.6


def verify_direct_link(url: str, title: str, timeout: int = 15) -> bool:
    """Load a candidate direct-job page and confirm it is live and about this
    job: HTTP success, not a "job closed" page, contains the title, and not on
    the blocklist. Never raises."""
    if not is_direct_candidate(url):
        return False
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except requests.RequestException:
        return False
    if r.status_code != 200:
        return False
    text = _page_text(r.text)
    if _looks_closed(text):
        return False
    return _contains_title(text, title)


# ---------------------------------------------------------------------------
# Resolution methods
# ---------------------------------------------------------------------------


def _follow_redirect_to_direct(url: str, title: str) -> tuple[str | None, bool]:
    """GET the listing and follow redirects (no login). Returns (final_url,
    is_right_job) where final_url is set only when the final address is on a
    different, non-aggregator domain."""
    if not url:
        return None, False
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
    except requests.RequestException:
        return None, False
    final = str(r.url or "")
    if not final or not is_direct_candidate(final):
        return None, False
    if host_of(final) == host_of(url):
        return None, False  # never left the aggregator
    text = _page_text(r.text)
    right = (
        r.status_code == 200
        and not _looks_closed(text)
        and _contains_title(text, title)
    )
    return final, right


def _match_board(kind: str, slug: str, title: str, location: str) -> str | None:
    """Find the exact posting on one ATS board by fuzzy title (+ location)."""
    try:
        jobs = fetch_board(kind, slug)
    except Exception:
        return None
    for j in jobs or []:
        if not title_matches(j.get("title", ""), title):
            continue
        if not locations_compatible(j.get("location", ""), location):
            continue
        u = (j.get("url") or "").strip()
        if is_direct_candidate(u):
            return u
    return None


def _cached_board(db: Session, company: str) -> tuple[str, str] | None:
    if not company:
        return None
    norm = _norm_name(company)
    for c in db.scalars(select(Company)).all():
        if c.ats and c.slug and _norm_name(c.name) == norm:
            return c.ats, c.slug
    return None


def _ats_lookup(db: Session, company: str, title: str, location: str) -> str | None:
    """Step C: try the company's cached board first, then guess slugs across the
    verified ATS endpoints and match the exact posting."""
    if not company or not title:
        return None
    cached = _cached_board(db, company)
    if cached:
        url = _match_board(cached[0], cached[1], title, location)
        if url:
            return url
    for kind in _ATS_PROBE_KINDS:
        for slug in build_slugs(company):
            url = _match_board(kind, slug, title, location)
            if url:
                add_company(db, company, kind, slug, auto_added=True)
                return url
    return None


def _search_candidates(query: str) -> list[str]:
    out: list[str] = []
    for engine in (_ddg_results, _bing_results):
        try:
            for u in engine(query):
                if u and u not in out:
                    out.append(u)
        except Exception:
            continue  # a search failure must never stop the resolve
    return out


def _search_job(company: str, title: str) -> str | None:
    """Step D: search for the exact job, prefer ATS/company domains, and verify
    before returning (a search result is a guess, so it must be checked)."""
    if not company.strip():
        return None
    query = f'"{company}" "{title}" careers'
    candidates = _search_candidates(query)
    # Accept known ATS domains outright. For anything else, the company's name
    # must be in the *domain* — a mirror site that embeds the company in its URL
    # path is an aggregator, not the employer, and is worse than no link.
    preferred = [u for u in candidates if _is_search_ats(u)]
    rest = [u for u in candidates if _domain_relevant(company, u)]
    for u in (preferred + rest)[:8]:
        if not is_direct_candidate(u):
            continue
        if verify_direct_link(u, title):
            return u
    return None


def _search_careers_page(company: str) -> str | None:
    """Step E: the company's own careers/jobs page, from its own domain only (a
    mirror board that embeds the company in its URL path is rejected)."""
    if not company.strip():
        return None
    candidates = _search_candidates(f"{company} careers")
    own = [
        u for u in candidates
        if is_direct_candidate(u) and _domain_relevant(company, u)
    ]
    if not own:
        return None
    careers = next(
        (u for u in own if re.search(r"career|jobs|join-us|work-with-us", u, re.I)),
        None,
    )
    return _root(careers or own[0])


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------


def resolve_job(db: Session, job: Job) -> ResolveResult:
    """Resolve one job's direct link. Never raises — a normal "not found" is
    ResolveResult(link_type=original)."""
    url = (job.url or "").strip()
    company = (job.company or "").strip()
    title = (job.title or "").strip()
    location = (job.location or "").strip()

    try:
        # A) The stored URL already points off the aggregator (source-provided).
        if is_direct_candidate(url):
            return ResolveResult(url, DIRECT_JOB, VIA_SOURCE_FIELD)

        # B) Follow redirects.
        final, right = _follow_redirect_to_direct(url, title)
        if final:
            if right:
                return ResolveResult(final, DIRECT_JOB, VIA_REDIRECT)
            # Landed on the company but not the exact job — keep it as a careers
            # page only if it looks like one (ATS or a careers/jobs path).
            if _is_ats(final) or re.search(r"career|jobs|join|work-with-us|apply", final, re.I):
                return ResolveResult(_root(final) or final, CAREERS_PAGE, VIA_REDIRECT)

        # C) ATS lookup by guessed board slug.
        hit = _ats_lookup(db, company, title, location)
        if hit:
            return ResolveResult(hit, DIRECT_JOB, VIA_ATS)

        # D) Web search for the exact job.
        found = _search_job(company, title)
        if found:
            return ResolveResult(found, DIRECT_JOB, VIA_SEARCH)

        # E) Careers page fallback.
        careers = _search_careers_page(company)
        if careers:
            return ResolveResult(careers, CAREERS_PAGE, VIA_CAREERS_PAGE)

        # F) Nothing found.
        return ResolveResult(None, ORIGINAL, VIA_NONE)
    except Exception as exc:  # belt and braces — the caller must never see a 500
        print(f"[resolver] failed for job {job.id}: {exc}", file=sys.stderr)
        return ResolveResult(None, ORIGINAL, VIA_NONE)


# ---------------------------------------------------------------------------
# Batch resolution (scan + backfill)
# ---------------------------------------------------------------------------


def jobs_due_for_resolution(db: Session, limit: int | None = None) -> list[Job]:
    """Jobs that still need resolving: no direct_url yet, and either never tried
    or last tried as "original" more than a day ago."""
    now = datetime.utcnow()
    cutoff = now - RETRY_AFTER
    empty_url = or_(Job.direct_url.is_(None), Job.direct_url == "")
    never = Job.resolved_at.is_(None)
    retryable = and_(Job.link_type == ORIGINAL, Job.resolved_at < cutoff)
    q = (
        db.query(Job)
        .filter(Job.stage != "Closed")
        .filter(empty_url, or_(never, retryable))
        .order_by(Job.score.desc())
    )
    return q.limit(limit).all() if limit else q.all()


def resolve_due_jobs(
    db: Session,
    limit: int | None = None,
    delay: float = RESOLVE_DELAY,
    on_progress=None,
) -> dict:
    """Resolve due jobs in place and commit. Returns a summary dict."""
    jobs = jobs_due_for_resolution(db, limit)
    stats = {
        DIRECT_JOB: 0,
        CAREERS_PAGE: 0,
        ORIGINAL: 0,
        "failed": 0,
        "by_method": {},
    }
    for job in jobs:
        try:
            result = resolve_job(db, job)
        except Exception as exc:
            print(f"[resolver] job {job.id} failed: {exc}", file=sys.stderr)
            stats["failed"] += 1
            continue
        job.direct_url = result.direct_url
        job.link_type = result.link_type
        job.resolved_via = result.resolved_via
        job.resolved_at = datetime.utcnow()
        stats[result.link_type] = stats.get(result.link_type, 0) + 1
        stats["by_method"][result.resolved_via] = (
            stats["by_method"].get(result.resolved_via, 0) + 1
        )
        if on_progress:
            on_progress(job.id, result)
        time.sleep(delay)
    db.commit()
    return stats
