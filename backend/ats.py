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
- Recruitee:   https://{slug}.recruitee.com/api/offers
- Teamtailor:  https://{slug}.teamtailor.com/jobs.json (JSON Feed)
- RSS:         any RSS/Atom jobs feed (the slug is the full feed URL)
- Optiver:     custom — parses https://www.optiver.com/sitemap.xml

Rejected:
- SmartRecruiters: robots.txt `Disallow: /` for all bots.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET

from .custom_scrapers import fetch_ashby, fetch_greenhouse, fetch_lever
from .http_client import get_json, get_text

# ATS kinds whose public endpoint was verified live today.
VERIFIED_ATS = (
    "greenhouse", "lever", "ashby", "workable",
    "recruitee", "teamtailor", "rss", "optiver",
)

# Implemented but not verified — fetch_board will still try, and return [].
UNVERIFIED_ATS = ()

ATS_KINDS = tuple(VERIFIED_ATS) + tuple(UNVERIFIED_ATS)


def is_ats_url(url: str) -> bool:
    """True if this URL is a direct company ATS link (vs an aggregator)."""
    return detect_ats(url)[0] is not None


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
    """Recruitee's public offers API (verified live)."""
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


def fetch_teamtailor(slug: str) -> list[dict]:
    """Teamtailor's public job board exposes a JSON Feed at
    {slug}.teamtailor.com/jobs.json (verified live)."""
    data = get_json(f"https://{slug}.teamtailor.com/jobs.json")
    if not isinstance(data, dict):
        return []
    out: list[dict] = []
    for it in data.get("items") or []:
        if not isinstance(it, dict):
            continue
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        if not title or not url:
            continue
        jp = it.get("_jobposting") or {}
        company = slug
        if isinstance(jp, dict):
            org = jp.get("hiringOrganization") or {}
            if isinstance(org, dict) and org.get("name"):
                company = str(org.get("name")).strip() or slug
        out.append({
            "source": f"teamtailor:{slug}",
            "title": title,
            "company": company,
            "location": _teamtailor_location(jp) or "Remote",
            "url": url,
            "description": _strip_html(it.get("content_html") or "")[:6000],
            "posted": it.get("date_published") or "",
            "tags": [],
        })
    return out


def _teamtailor_location(jp) -> str:
    if not isinstance(jp, dict):
        return ""
    loc = jp.get("jobLocation") or jp.get("location") or ""
    places = loc if isinstance(loc, list) else [loc]
    parts: list[str] = []
    for p in places:
        if isinstance(p, dict):
            addr = p.get("address") or {}
            if isinstance(addr, dict):
                seg = ", ".join(
                    str(addr.get(k))
                    for k in ("addressLocality", "addressRegion", "addressCountry")
                    if addr.get(k)
                )
                if seg:
                    parts.append(seg)
                    continue
            if p.get("name"):
                parts.append(str(p.get("name")))
    return " / ".join(parts)


def fetch_rss_board(slug: str) -> list[dict]:
    """A generic RSS/Atom jobs feed (e.g. a WordPress jobs feed). The channel
    title becomes the company name; each item is a job. `slug` is the feed URL."""
    feed_url = (slug or "").strip()
    text = get_text(feed_url)
    if not text:
        return []
    try:
        root = ET.fromstring(text)
    except Exception:
        return []
    company = ""
    channel = root.find("channel")
    if channel is not None:
        ct = channel.find("title")
        if ct is not None and ct.text:
            company = ct.text.strip()
    # WordPress jobs feeds often title the channel "Jobs – Company" — keep just
    # the company.
    company = re.sub(
        r"^(jobs|careers|vacatures|vacancies|open positions)\s*[-\u2013\u2014:|]+\s*",
        "", company, flags=re.I,
    ).strip()
    out: list[dict] = []
    for item in root.iter("item"):
        def g(tag):
            el = item.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""
        title = g("title")
        link = g("link")
        if not title or not link:
            continue
        out.append({
            "source": f"rss:{company or feed_url[:24]}",
            "title": title,
            "company": company,
            "location": "Remote",
            "url": link,
            "description": _strip_html(g("description") or g("summary"))[:6000],
            "posted": g("pubDate") or g("updated"),
            "tags": [],
        })
    return out


def fetch_optiver(slug: str = "") -> list[dict]:
    """Optiver's careers are a custom site, but its sitemap lists every
    /join-us/jobs/ posting. Parse the sitemap and derive the title and location
    from the URL path (department/city/slug). Titles are approximate (no
    description is fetched), which is a known limit."""
    xml = get_text("https://www.optiver.com/sitemap.xml")
    if not xml:
        return []
    urls = re.findall(r"<loc>(https?://[^<]+)</loc>", xml)
    out: list[dict] = []
    seen: set[str] = set()
    for u in urls:
        if "/join-us/jobs/" not in u:
            continue
        path = u.rstrip("/").split("/join-us/jobs/", 1)[-1]
        parts = [p for p in path.split("/") if p]
        if len(parts) < 2 or u in seen:
            continue
        dept = parts[0]
        slug = parts[-1]
        city = parts[1] if len(parts) >= 3 else ""
        if not slug:
            continue
        seen.add(u)
        out.append({
            "source": "optiver",
            "title": re.sub(r"\s+", " ", slug.replace("-", " ")).strip().title(),
            "company": "Optiver",
            "location": re.sub(r"\s+", " ", city.replace("-", " ")).strip().title() or "Amsterdam",
            "url": u,
            "description": "",
            "posted": "",
            "tags": [dept.replace("-", " ")],
        })
    return out


_FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workable": fetch_workable,
    "recruitee": fetch_recruitee,
    "teamtailor": fetch_teamtailor,
    "rss": fetch_rss_board,
    "optiver": fetch_optiver,
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
