"""Best-effort ATS board discovery via free web search (Part 2C).

Verified live: free search engines largely block `site:` queries from automated
clients — DuckDuckGo returns an anti-bot challenge, Bing returns no `site:`
results, and Mojeek's robots.txt disallows `/search`. So this pass is kept
strictly capped and rate-limited, never raises, and in practice returns few or
no boards. The auto-grow registry (Part 2B) is the effective discovery path.
"""
from __future__ import annotations

import re

from .ats import detect_ats
from .http_client import get_text

_ATS_DOMAINS = (
    "boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
    "apply.workable.com",
)

# Hard cap on search requests per run, across all titles and engines.
MAX_QUERIES = 6
_SEARCH_TIMEOUT = 12


def _extract_boards(text: str) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    if not text:
        return found
    for url in re.findall(r"https?://[^\s\"'<>]+", text):
        kind, slug = detect_ats(url)
        if kind and slug:
            found.add((kind, slug))
    return found


def _ddg(query: str) -> str | None:
    return get_text(
        "https://html.duckduckgo.com/html/", params={"q": query}, timeout=_SEARCH_TIMEOUT
    )


def _bing(query: str) -> str | None:
    return get_text(
        "https://www.bing.com/search",
        params={"q": query, "format": "rss"},
        timeout=_SEARCH_TIMEOUT,
    )


def discover_boards(titles: list[str]) -> set[tuple[str, str]]:
    """Search for public ATS board pages matching the user's target titles.

    Returns a set of (ats_kind, slug). Never raises; caps queries per run."""
    found: set[tuple[str, str]] = set()
    queries_done = 0
    for title in (titles or [])[:4]:
        for domain in _ATS_DOMAINS:
            query = f'site:{domain} "{title}"'
            for engine in (_ddg, _bing):
                if queries_done >= MAX_QUERIES:
                    return found
                queries_done += 1
                try:
                    text = engine(query)
                    if text:
                        found |= _extract_boards(text)
                except Exception:
                    continue  # a search failure must never stop the scan
    return found
