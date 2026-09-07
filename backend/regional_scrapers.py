"""Region-specific job boards, for locations the remote-only boards never cover.

Kept out of fetch_jobs_vendored.py on purpose: that file mirrors the standalone
fetch_jobs.py scraper script, so app-only sources live here instead. Same
contract as the other fetchers — a norm()-shaped dict per job, and any failure
returns [] rather than raising, so one dead board never sinks a scan.

Pakistan (Mustakbil.com)
    Rozee.pk, the obvious first choice, sits behind a Cloudflare challenge and
    cannot be read with plain HTTP. Mustakbil serves its country, city, and
    category listings as server-rendered HTML, so we read those and filter by the
    search term locally (the same trick fetch_arbeitnow uses).
"""
from __future__ import annotations

import sys
import time

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

MUSTAKBIL_BASE = "https://www.mustakbil.com"

# City landing pages we know exist. A configured location naming one of these
# cities narrows the fetch to it; anything else Pakistan-wide uses the country
# page plus the categories a PM/partnerships search actually lands in.
MUSTAKBIL_CITIES = {
    "islamabad", "karachi", "lahore", "rawalpindi", "faisalabad",
    "multan", "peshawar", "quetta", "sialkot", "hyderabad",
}
MUSTAKBIL_CATEGORIES = [
    "information-technology",
    "advertising-marketing-public-relations",
    "sales",
    "web-e-commerce",
]

# Words that carry no signal when matching a search term against a listing.
_STOP = {"a", "an", "the", "of", "and", "for", "to", "in", "at", "senior", "lead"}

# One scan runs every search term against every source, but Mustakbil's listing
# pages do not vary by term — we filter locally. Cache each page for the length
# of a scan so 20 search terms cost one fetch, not twenty.
_PAGE_TTL = 600  # seconds
_page_cache: dict[str, tuple[float, str]] = {}


def _norm(j: dict) -> dict:
    """Same shape every other fetcher returns."""
    return {
        "source": j.get("source", "unknown"),
        "title": (j.get("title") or "").strip(),
        "company": (j.get("company") or "").strip(),
        "location": (j.get("location") or "").strip(),
        "url": (j.get("url") or "").strip(),
        "description": (j.get("description") or "")[:6000],
        "posted": j.get("posted", ""),
        "tags": j.get("tags", []),
    }


def is_pakistan_location(location: str) -> bool:
    """True if this configured location is somewhere Mustakbil covers."""
    loc = (location or "").strip().lower()
    if not loc:
        return False
    return "pakistan" in loc or any(city in loc for city in MUSTAKBIL_CITIES)


def _get_page(url: str) -> str | None:
    now = time.time()
    hit = _page_cache.get(url)
    if hit and now - hit[0] < _PAGE_TTL:
        return hit[1]
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        r.encoding = "utf-8"  # the server does not always declare it
        _page_cache[url] = (now, r.text)
        return r.text
    except Exception as exc:
        print(f"  [mustakbil] {url} failed: {exc}", file=sys.stderr)
        return None


def _matches(query: str, blob: str) -> bool:
    """Loose relevance: most of the meaningful words in the search term appear in
    the listing. Strict substring matching would drop 'Product Manager' from a
    'senior product manager' search."""
    tokens = [t for t in query.lower().split() if len(t) > 2 and t not in _STOP]
    if not tokens:
        return True
    hits = sum(1 for t in tokens if t in blob)
    return hits / len(tokens) >= 0.6


def _mustakbil_pages(location: str) -> list[str]:
    loc = (location or "").strip().lower()
    city = next((c for c in MUSTAKBIL_CITIES if c in loc), None)
    if city:
        return [f"{MUSTAKBIL_BASE}/jobs/pakistan/{city}"]
    return [f"{MUSTAKBIL_BASE}/jobs/pakistan"] + [
        f"{MUSTAKBIL_BASE}/jobs/pakistan/{c}" for c in MUSTAKBIL_CATEGORIES
    ]


def _parse_card(card) -> dict | None:
    # The cards render Material icons as ligature text ("place", "payments")
    # inside the very elements we read. Drop them or they end up in the location.
    for icon in card.select("i.icon"):
        icon.decompose()

    link = card.select_one("h3.jl-title a")
    if link is None:
        return None
    href = link.get("href", "")
    if not href:
        return None
    url = href if href.startswith("http") else f"{MUSTAKBIL_BASE}{href}"

    def text(selector: str) -> str:
        el = card.select_one(selector)
        return el.get_text(" ", strip=True) if el else ""

    location = text("p.jl-location") or "Pakistan"
    salary = text(".jl-salary")
    chips = " ".join(
        c.get_text(" ", strip=True) for c in card.select(".jl-chip")
    )
    desc = text(".jl-desc")
    # The card is all Mustakbil renders without a second request per job. Fold
    # the salary and the type chips in so scoring and salary parsing see them.
    description = " ".join(p for p in (desc, salary, chips) if p)
    return _norm({
        "source": "mustakbil",
        "title": link.get_text(" ", strip=True),
        "company": text("p.jl-company .jl-company__name"),
        "location": location,
        "url": url,
        "description": description,
        "posted": text(".jl-time"),
    })


def fetch_mustakbil(q: str, location: str = "Pakistan") -> list:
    """Pakistan-based roles (on-site, hybrid and remote) from Mustakbil.com."""
    results: list[dict] = []
    seen: set[str] = set()
    try:
        for page_url in _mustakbil_pages(location):
            html = _get_page(page_url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for card in soup.select("article.jl-card"):
                job = _parse_card(card)
                if not job or not job["title"] or job["url"] in seen:
                    continue
                blob = f"{job['title']} {job['description']}".lower()
                if not _matches(q, blob):
                    continue
                seen.add(job["url"])
                results.append(job)
            time.sleep(0.3)
    except Exception as exc:
        print(f"  [mustakbil] '{q}' failed: {exc}", file=sys.stderr)
    return results
