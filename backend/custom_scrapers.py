"""User-added job sources and single-job-by-URL fetching.

Reliable source kinds:
- rss:        any job-board RSS/Atom feed URL
- greenhouse: a company's Greenhouse board (public JSON API)
- lever:      a company's Lever board (public JSON API)
Best-effort:
- url:        scrape a generic careers/job page (many sites block this)
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from typing import Callable

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "career-copilot/0.8.3 (+https://github.com/SyedmaazSaif/"
        "career-copilot; local job-search assistant)"
    ),
    "Accept": "application/json, text/html, application/xml, */*",
}


def _norm(source: str, title: str, company: str, location: str, url: str,
          description: str, posted: str = "") -> dict:
    return {
        "source": source,
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "location": (location or "Remote").strip(),
        "url": (url or "").strip(),
        "description": (description or "")[:6000],
        "posted": posted or "",
        "tags": [],
    }


def _strip_html(html: str) -> str:
    try:
        return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
    except Exception:
        return html or ""


def fetch_rss(url: str, label: str = "") -> list[dict]:
    src = f"rss:{label or url[:24]}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        out = []
        for item in root.iter():
            tag = item.tag.split("}")[-1]
            if tag not in ("item", "entry"):
                continue

            def get(name):
                for child in item:
                    if child.tag.split("}")[-1] == name:
                        return (child.text or "").strip() if child.text else (
                            child.attrib.get("href", "")
                        )
                return ""

            link = get("link")
            title = get("title")
            if not link or not title:
                continue
            desc = _strip_html(get("description") or get("summary") or get("content"))
            out.append(_norm(src, title, "", "Remote", link, desc, get("pubDate") or get("updated")))
        return out
    except Exception as exc:
        print(f"[custom rss] {url} failed: {exc}", file=sys.stderr)
        return []


def fetch_greenhouse(company: str) -> list[dict]:
    slug = company.strip().rstrip("/").split("/")[-1]
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
            headers=HEADERS, timeout=25,
        )
        if r.status_code != 200:
            return []
        out = []
        for j in r.json().get("jobs", []):
            out.append(_norm(
                f"greenhouse:{slug}",
                j.get("title", ""),
                (j.get("company_name") or slug),
                (j.get("location", {}) or {}).get("name", "Remote"),
                j.get("absolute_url", ""),
                _strip_html(j.get("content", "")),
                j.get("updated_at", ""),
            ))
        return out
    except Exception as exc:
        print(f"[greenhouse] {company} failed: {exc}", file=sys.stderr)
        return []


def fetch_lever(company: str) -> list[dict]:
    slug = company.strip().rstrip("/").split("/")[-1]
    try:
        r = requests.get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json",
            headers=HEADERS, timeout=25,
        )
        if r.status_code != 200:
            return []
        out = []
        for j in r.json():
            cat = j.get("categories", {}) or {}
            out.append(_norm(
                f"lever:{slug}",
                j.get("text", ""),
                slug,
                cat.get("location", "Remote"),
                j.get("hostedUrl", ""),
                _strip_html(j.get("descriptionPlain") or j.get("description", "")),
                "",
            ))
        return out
    except Exception as exc:
        print(f"[lever] {company} failed: {exc}", file=sys.stderr)
        return []


def fetch_ashby(company: str) -> list[dict]:
    """A company's Ashby board (public JSON API)."""
    slug = company.strip().rstrip("/").split("/")[-1]
    try:
        r = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            headers=HEADERS, timeout=25,
        )
        if r.status_code != 200:
            return []
        out = []
        for j in r.json().get("jobs", []):
            loc = j.get("location")
            if isinstance(loc, dict):
                loc = loc.get("name") or "Remote"
            out.append(_norm(
                f"ashby:{slug}",
                j.get("title", ""),
                slug,
                loc or "Remote",
                j.get("jobUrl") or j.get("applyUrl", ""),
                _strip_html(j.get("descriptionHtml") or j.get("description", "")),
                j.get("publishedAt", ""),
            ))
        return out
    except Exception as exc:
        print(f"[ashby] {company} failed: {exc}", file=sys.stderr)
        return []


def fetch_single_job(url: str) -> dict | None:
    """Best-effort extraction of one job posting from a page URL."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")

        def meta(prop):
            el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            return el.get("content", "").strip() if el else ""

        title = meta("og:title") or (soup.title.get_text(strip=True) if soup.title else "")
        h1 = soup.find("h1")
        if h1 and len(h1.get_text(strip=True)) > 3:
            title = title or h1.get_text(strip=True)
        company = meta("og:site_name")
        # body text as description
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        body = soup.get_text(" ", strip=True)
        description = meta("og:description") or body[:6000]
        if not title:
            return None
        return _norm("manual", title, company, "Unknown", url, description)
    except Exception as exc:
        print(f"[single job] {url} failed: {exc}", file=sys.stderr)
        return None


def fetch_generic(url: str, label: str = "") -> list[dict]:
    """Very best-effort: treat the page as a single posting."""
    job = fetch_single_job(url)
    if job:
        job["source"] = f"url:{label or url[:24]}"
    return [job] if job else []


def _detect_ats(text: str) -> tuple[str | None, str | None]:
    """Find a known applicant-tracking-system board in a URL or HTML string.
    Returns (kind, slug)."""
    t = text or ""
    m = re.search(r"greenhouse\.io/embed/job_board\?for=([a-z0-9-]+)", t)
    if m:
        return ("greenhouse", m.group(1))
    m = re.search(r"boards\.greenhouse\.io/([a-z0-9-]+)", t)
    if m:
        return ("greenhouse", m.group(1))
    m = re.search(r"jobs\.lever\.co/([a-z0-9-]+)", t)
    if m:
        return ("lever", m.group(1))
    m = re.search(r"jobs\.ashbyhq\.com/([a-z0-9-]+)", t)
    if m:
        return ("ashby", m.group(1))
    return (None, None)


def _fetch_by_kind(kind: str, slug: str, label: str = "") -> list[dict]:
    if kind == "greenhouse":
        return fetch_greenhouse(slug)
    if kind == "lever":
        return fetch_lever(slug)
    if kind == "ashby":
        return fetch_ashby(slug)
    return []


def fetch_company(url: str, label: str = "") -> list[dict]:
    """Scan a company's careers page: detect its ATS and pull the whole board.
    Falls back to treating the page as a single posting."""
    kind, slug = _detect_ats(url)
    if kind:
        return _fetch_by_kind(kind, slug, label)
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code == 200:
            kind, slug = _detect_ats(r.text)
            if kind:
                return _fetch_by_kind(kind, slug, label)
    except Exception as exc:
        print(f"[company] {url} failed: {exc}", file=sys.stderr)
    return fetch_generic(url, label)


_DISPATCH: dict[str, Callable] = {
    "rss": fetch_rss,
    "greenhouse": lambda v, label="": fetch_greenhouse(v),
    "lever": lambda v, label="": fetch_lever(v),
    "ashby": lambda v, label="": fetch_ashby(v),
    "company": fetch_company,
    "url": fetch_generic,
}


def run_custom_sources(
    sources: list, on_progress: Callable[[str, int, int], None] | None = None
) -> tuple[list[dict], dict]:
    """sources: list of objects with .kind, .value, .label, .enabled."""
    jobs: list[dict] = []
    counts: dict[str, int] = {}
    seen: set[str] = set()
    for s in sources:
        if not getattr(s, "enabled", True):
            continue
        fn = _DISPATCH.get(s.kind)
        if not fn or not s.value:
            continue
        try:
            batch = fn(s.value, s.label) if s.kind in ("rss", "url", "company") else fn(s.value)
        except Exception as exc:
            print(f"[custom {s.kind}] {s.value} failed: {exc}", file=sys.stderr)
            batch = []
        added = 0
        for j in batch:
            u = j.get("url", "")
            if not u or u in seen:
                continue
            seen.add(u)
            jobs.append(j)
            added += 1
        name = f"{s.kind}:{s.label or s.value}"[:40]
        counts[name] = added
        if on_progress:
            on_progress(name, added, len(jobs))
    return jobs, counts
