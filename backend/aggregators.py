"""Free aggregator job sources verified to allow automated access.

- The Muse: public JSON API (no key).
- Hacker News "Who is hiring?": the monthly thread, read via the public
  HN/Algolia API. Postings are free-text, so parsing is best-effort.

Every fetcher returns job dicts in the app's standard shape and never raises.
"""
from __future__ import annotations

import html
import re

from .http_client import get_json

# Pages of The Muse to pull per scan (20 jobs per page).
MUSE_PAGES = 2


def _strip_html(text: str) -> str:
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)
    except Exception:
        return text or ""


def fetch_muse() -> list[dict]:
    """The Muse public jobs API (verified live)."""
    out: list[dict] = []
    for page in range(MUSE_PAGES):
        data = get_json(
            "https://www.themuse.com/api/public/jobs", params={"page": page}
        )
        if not isinstance(data, dict):
            break
        for r in data.get("results") or []:
            if not isinstance(r, dict):
                continue
            title = (r.get("name") or "").strip()
            company = (r.get("company") or {}).get("name", "")
            url = (r.get("refs") or {}).get("landing_page", "")
            if not title or not url:
                continue
            loc = ", ".join(
                l.get("name", "")
                for l in (r.get("locations") or [])
                if isinstance(l, dict)
            )
            tags = [
                c.get("name", "")
                for c in (r.get("categories") or [])
                if isinstance(c, dict)
            ]
            out.append({
                "source": "muse",
                "title": title,
                "company": company,
                "location": loc or "Remote",
                "url": url,
                "description": _strip_html(r.get("contents") or "")[:6000],
                "posted": r.get("publication_date") or "",
                "tags": tags,
            })
    return out


def _hn_clean(text: str) -> str:
    t = html.unescape(text or "")
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _latest_hiring_story() -> dict | None:
    data = get_json(
        "https://hn.algolia.com/api/v1/search_by_date",
        params={"query": "who is hiring", "tags": "story", "hitsPerPage": 25},
    )
    if not isinstance(data, dict):
        return None
    for h in data.get("hits") or []:
        title = (h.get("title") or "").lower()
        if "who is hiring" in title and "ask hn" in title:
            return h
    return None


def fetch_hackernews() -> list[dict]:
    """The current 'Ask HN: Who is hiring?' thread, via the public Algolia API.

    Each top-level comment is a job posting. Best-effort: the first line is the
    header ("Company (Location) — Role"), and the first link is the apply URL."""
    story = _latest_hiring_story()
    if not story:
        return []
    sid = story.get("objectID")
    data = get_json(f"https://hn.algolia.com/api/v1/items/{sid}")
    if not isinstance(data, dict):
        return []
    out: list[dict] = []
    for c in data.get("children") or []:
        if not isinstance(c, dict):
            continue
        text = _hn_clean(c.get("text") or "")
        if not text:
            continue
        first_line = text.split("\n")[0].strip() or text[:120]
        company = ""
        location = ""
        m = re.match(r"^(.*?)\s*\((.*?)\)", first_line)
        if m:
            company = m.group(1).strip()
            location = m.group(2).strip()
        else:
            company = re.split(r"\s*[—–-]\s*", first_line, 1)[0].strip()
        url = ""
        murl = re.search(r"https?://[^\s)\],;]+", text)
        if murl:
            url = murl.group(0).rstrip(".,;")
        out.append({
            "source": "hackernews",
            "title": first_line,
            "company": company,
            "location": location or "Remote",
            "url": url,
            "description": text[:6000],
            "posted": story.get("created_at") or "",
            "tags": [],
        })
    return out
