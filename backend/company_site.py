"""Best-effort lookup of the company's own application page.

Aggregator listings are often paywalled, expired, or a wrapper around the real
posting, so the user prefers to apply on the company's own careers site. Two
cheap strategies, in order:

1. Follow the listing URL's redirects. Many boards bounce straight to the
   employer's ATS (Greenhouse, Lever, …) — that IS the direct application link.
2. Otherwise, search for "<company> careers" and take the best organic result:
   DuckDuckGo's HTML endpoint first, Bing's RSS when DuckDuckGo answers with its
   anti-bot challenge (it does, after a few requests in a row).

Search engines confidently return snapchat.com for "Snap Finance", so a result
must actually carry the company's name (_relevant) before we save it. A wrong
link is worse than none: the user would follow it and quietly apply nowhere.

Every failure path returns None. A lookup that finds nothing is a normal
outcome, never an error — the UI lets the user paste the link themselves.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Applicant tracking systems. A listing that lands on one of these is already
# hosted by the employer, so it is the direct application link.
ATS_HOSTS = (
    "greenhouse.io",
    "lever.co",
    "workable.com",
    "ashbyhq.com",
    "bamboohr.com",
    "smartrecruiters.com",
)

# Hosts that are never a company's own careers site.
_AGGREGATORS = (
    "duckduckgo.com", "google.", "bing.com", "linkedin.com", "indeed.",
    "glassdoor.", "remoteok.com", "remotive.com", "himalayas.app",
    "weworkremotely.com", "wellfound.com", "hiring.cafe", "arbeitnow.com",
    "remote.co", "ziprecruiter.com", "monster.com", "jobs.", "facebook.com",
    "twitter.com", "x.com", "youtube.com", "wikipedia.org", "crunchbase.com",
    "reddit.com", "mustakbil.com", "rozee.pk",
)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _is_ats(url: str) -> bool:
    host = _host(url)
    return any(host == h or host.endswith("." + h) for h in ATS_HOSTS)


def _is_aggregator(url: str) -> bool:
    host = _host(url)
    return any(a in host for a in _AGGREGATORS)


def _follow_redirects(url: str) -> str | None:
    """The listing's final destination after redirects, or None."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        return str(r.url) or None
    except Exception as exc:
        print(f"[company-site] redirect follow failed for {url}: {exc}", file=sys.stderr)
        return None


def _root(url: str) -> str:
    """Trim a deep ATS/careers URL back to something stable and pasteable."""
    try:
        p = urlparse(url)
        if not p.scheme or not p.hostname:
            return url
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except Exception:
        return url


def _unwrap_ddg(href: str) -> str:
    """DuckDuckGo's HTML results wrap targets as /l/?uddg=<encoded>."""
    if "duckduckgo.com/l/" in href or href.startswith("/l/"):
        try:
            qs = parse_qs(urlparse(href).query)
            target = qs.get("uddg", [""])[0]
            if target:
                return target
        except Exception:
            return href
    if href.startswith("//"):
        return "https:" + href
    return href


# Words in a company name that say nothing about its domain.
_NAME_NOISE = {
    "inc", "llc", "ltd", "limited", "gmbh", "corp", "corporation", "co", "plc",
    "the", "group", "holdings", "technologies", "technology", "labs", "company",
    "careers", "jobs",
}


def _relevant(company: str, url: str) -> bool:
    """Does this search result plausibly belong to this company?

    Search engines happily return snapchat.com for "Snap Finance careers". A
    wrong link saved silently is worse than no link at all — the user would open
    it, apply nowhere, and never know — so a result must carry the company's name
    (either whole, or its most distinctive word) somewhere in the URL.
    """
    words = [
        w for w in re.split(r"[^a-z0-9]+", company.lower())
        if len(w) >= 3 and w not in _NAME_NOISE
    ]
    if not words:
        return False
    compact = "".join(words)
    longest = max(words, key=len)
    target = url.lower()
    return compact in target or longest in target


def _pick(company: str, candidates: list[str]) -> str | None:
    """The best of a result list: a careers/jobs page for the right company if
    one is there, otherwise that company's site."""
    usable = [
        u for u in candidates
        if u.startswith(("http://", "https://"))
        and (_is_ats(u) or not _is_aggregator(u))
        and _relevant(company, u)
    ]
    if not usable:
        return None
    careers = next(
        (u for u in usable if re.search(r"career|jobs|join-us|work-with-us", u, re.I)),
        None,
    )
    return _root(careers or usable[0])


def _ddg_results(query: str) -> list[str]:
    """DuckDuckGo's HTML endpoint. It answers with an anti-bot challenge (202)
    if you ask too often, which we treat as simply having no results."""
    r = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers=HEADERS,
        timeout=20,
    )
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    return [
        _unwrap_ddg(a.get("href", ""))
        for a in soup.select("a.result__a, a.result__url")
    ]


def _bing_results(query: str) -> list[str]:
    """Bing's RSS output — the fallback for when DuckDuckGo challenges us. Noisier
    than DDG, which is exactly what _relevant() is there to catch."""
    r = requests.get(
        "https://www.bing.com/search",
        params={"q": query, "format": "rss"},
        headers=HEADERS,
        timeout=20,
    )
    if r.status_code != 200:
        return []
    root = ET.fromstring(r.content)
    return [link for i in root.iter("item") if (link := i.findtext("link"))]


def _search_careers(company: str) -> str | None:
    """Best organic result for "<company> careers", or None."""
    if not company.strip():
        return None
    query = f"{company} careers"
    for engine in (_ddg_results, _bing_results):
        try:
            hit = _pick(company, engine(query))
            if hit:
                return hit
        except Exception as exc:
            print(
                f"[company-site] {engine.__name__} failed for {company!r}: {exc}",
                file=sys.stderr,
            )
    return None


def find_company_site(job_url: str, company: str) -> str | None:
    """Resolve the company's application page. Returns None if nothing is found;
    never raises."""
    try:
        final = _follow_redirects(job_url) if job_url else None
        if final and _is_ats(final):
            return _root(final)
        # A listing that redirected off the aggregator onto the employer's own
        # domain is just as good a direct link.
        if final and not _is_aggregator(final) and _host(final) != _host(job_url):
            return _root(final)
        return _search_careers(company)
    except Exception as exc:  # belt and braces — the caller must never see a 500
        print(f"[company-site] lookup failed: {exc}", file=sys.stderr)
        return None
