"""Aggregator/job-board blocklist for the direct-link resolver.

Domains listed in `aggregator_blocklist.json` are never accepted as a "direct"
company link. The list lives in a plain JSON file so it can be edited without
touching code — one domain per line.

Matching (case-insensitive):
- the host equals an entry, or is a subdomain of it (`foo.indeed.com`), or
- the entry ends in a dot (a fragment like `google.` or `indeed.`) and appears
  anywhere in the host — this covers multi-TLD boards (`indeed.co.uk`,
  `glassdoor.de`) without enumerating every country.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

_BLOCKLIST_PATH = Path(__file__).resolve().parent / "aggregator_blocklist.json"

_domains: list[str] | None = None


def blocklisted_domains() -> list[str]:
    """The loaded blocklist entries (lowercased). Cached in-process."""
    global _domains
    if _domains is None:
        try:
            data = json.loads(_BLOCKLIST_PATH.read_text(encoding="utf-8"))
            raw = data.get("blocked_domains", []) if isinstance(data, dict) else data
            _domains = [
                str(d).strip().lower().rstrip("/")
                for d in raw
                if str(d).strip()
            ]
        except Exception:
            _domains = []
    return _domains


def host_of(url: str) -> str:
    """Lowercase hostname of a URL, or '' when it can't be parsed."""
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def is_blocked(url: str) -> bool:
    """True when this URL is on an aggregator/job-board domain."""
    host = host_of(url)
    if not host:
        return False
    for entry in blocklisted_domains():
        if not entry:
            continue
        if host == entry or host.endswith("." + entry):
            return True
        if entry.endswith(".") and entry in host:
            return True
    return False


def is_direct_candidate(url: str) -> bool:
    """True when a URL looks like a plausible direct company link: http(s), has
    a host, and is not on the blocklist."""
    return bool(
        url
        and url.startswith(("http://", "https://"))
        and host_of(url)
        and not is_blocked(url)
    )
