"""Applicant-tracking-system (ATS) connectors and detection.

Each ATS publishes a free, public job-board feed meant for apps to read. Every
connector returns a list of job dicts in the app's standard shape
(title, company, location, url, description, posted, source) and never raises,
so one dead board can never sink a scan.

Verified live before shipping (robots.txt + a real request):
- Greenhouse:  https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
- Lever:       https://api.lever.co/v0/postings/{slug}?mode=json
- Ashby:       https://api.ashbyhq.com/posting-api/job-board/{slug}
- Workable:    https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true

Rejected:
- SmartRecruiters: robots.txt `Disallow: /` for all bots.

Unverified (connector kept but not in the default set):
- Recruitee: the old `{company}.recruitee.com/api/offers` pattern now 404s on
  every subdomain tried and `app.recruitee.com` is an auth-gated HTML app, so no
  live public endpoint could be confirmed.
"""
from __future__ import annotations

import re
import sys

from .custom_scrapers import fetch_ashby, fetch_greenhouse, fetch_lever
from .http_client import get_json

# ATS kinds whose public endpoint was verified live today.
VERIFIED_ATS = ("greenhouse", "lever", "ashby", "workable")

# Implemented but not verified — fetch_board will still try, and return [].
UNVERIFIED_ATS = ("recruitee",)

ATS_KINDS = tuple(VERIFIED_ATS) + tuple(UNVERIFIED_ATS)


def detect_ats(url: str) -> tuple[str | None, str | None]:
    """Detect an ATS and its board slug from a URL. Returns (kind, slug) or
    (None, None). Only board URLs are detected, not single-job deep links."""
    t = (url or "").lower()
    m = re.search(r"boards\.greenhouse\.io/([a-z0-9-]+)", t)
    if m:
        return ("greenhouse", m.group(1))
    m = re.search(r"greenhouse\.io/embed/job_board\?for=([a-z0-9-]+)", t)
    if m:
        return ("greenhouse", m.group(1))
    m = re.search(r"jobs\.lever\.co/([a-z0-9-]+)", t)
    if m:
        return ("lever", m.group(1))
    m = re.search(r"jobs\.ashbyhq\.com/([a-z0-9-]+)", t)
    if m:
        return ("ashby", m.group(1))
    m = re.search(r"apply\.workable\.com/([a-z0-9-]+)", t)
    if m and m.group(1) not in ("j", "api", "widget", "accounts"):
        return ("workable", m.group(1))
    return (None, None)


def _strip_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
    except Exception:
        return html or ""


def fetch_workable(slug: str) -> list[dict]:
    """Workable's public job-board widget API (verified live)."""
    data = get_json(
        f"https://apply.workable.com/api/v1/widget/accounts/{slug}",
        params={"details": "true"},
    )
    if not isinstance(data, dict):
        return []
    company = (data.get("name") or slug).strip()
    jobs = data.get("jobs") or []
    out: list[dict] = []
    for j in jobs or []:
        if not isinstance(j, dict):
            continue
        title = (j.get("title") or "").strip()
        url = (j.get("application_url") or j.get("url") or "").strip()
        if not title or not url:
            continue
        loc = " / ".join(
            f"{l.get('city', '')} {l.get('country', '')}".strip()
            for l in (j.get("locations") or [])
            if isinstance(l, dict)
        )
        out.append({
            "source": f"workable:{slug}",
            "title": title,
            "company": company,
            "location": loc or "Remote",
            "url": url,
            "description": _strip_html(j.get("description") or "")[:6000],
            "posted": j.get("published_on") or j.get("created_at") or "",
            "tags": [],
        })
    return out


def fetch_recruitee(slug: str) -> list[dict]:
    """Recruitee's public offers API. NOT verified live — kept defensive so it
    returns [] rather than raising. See the module docstring."""
    data = get_json(f"https://{slug}.recruitee.com/api/offers")
    if not isinstance(data, dict):
        return []
    offers = data.get("offers") or []
    out: list[dict] = []
    for o in offers or []:
        if not isinstance(o, dict):
            continue
        title = (o.get("title") or "").strip()
        url = (o.get("careers_url") or o.get("url") or "").strip()
        if not title:
            continue
        out.append({
            "source": f"recruitee:{slug}",
            "title": title,
            "company": (o.get("company_name") or slug).strip(),
            "location": (o.get("location") or "Remote").strip(),
            "url": url,
            "description": _strip_html(o.get("description") or "")[:6000],
            "posted": o.get("created_at") or "",
            "tags": [],
        })
    return out


_FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workable": fetch_workable,
    "recruitee": fetch_recruitee,
}


def fetch_board(kind: str, slug: str) -> list[dict]:
    """Fetch all open jobs for one ATS board. Never raises; [] on failure."""
    fn = _FETCHERS.get(kind)
    if not fn or not slug:
        return []
    try:
        return fn(slug.strip())
    except Exception as exc:
        print(f"[ats:{kind}] {slug} failed: {exc}", file=sys.stderr)
        return []
