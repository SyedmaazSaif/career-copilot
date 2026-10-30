"""Polite HTTP for job sources.

Enforces the hard rules for talking to outside services:
- identify the app honestly in the User-Agent (no fake browser UA)
- rate-limit requests per host
- back off on 429 / 5xx errors
- cache successful responses so a scan does not hammer a host

Every function returns None on persistent failure instead of raising, so one
dead source can never sink a scan.
"""
from __future__ import annotations

import json
import threading
import time
from urllib.parse import urlparse

import requests

APP_NAME = "career-copilot"
APP_VERSION = "0.8.3"
APP_URL = "https://github.com/SyedmaazSaif/career-copilot"

USER_AGENT = f"{APP_NAME}/{APP_VERSION} (+{APP_URL}; local job-search assistant)"

DEFAULT_MIN_INTERVAL = 1.0  # seconds between requests to the same host
DEFAULT_CACHE_TTL = 600      # seconds a successful GET stays cached
DEFAULT_TIMEOUT = 30

_lock = threading.Lock()
_last_request: dict[str, float] = {}
_cache: dict[str, tuple[float, str]] = {}


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or url).lower()
    except Exception:
        return (url or "").lower()


def _cache_key(url: str, params: dict | None) -> str:
    try:
        r = requests.Request("GET", url, params=params).prepare()
        return r.url
    except Exception:
        return url


def _throttle(host: str, min_interval: float) -> None:
    with _lock:
        now = time.time()
        last = _last_request.get(host)
        if last is not None:
            wait = min_interval - (now - last)
            if wait > 0:
                time.sleep(wait)
        _last_request[host] = time.time()


def get_json(
    url: str,
    params: dict | None = None,
    *,
    min_interval: float = DEFAULT_MIN_INTERVAL,
    cache_ttl: float = DEFAULT_CACHE_TTL,
    timeout: int = DEFAULT_TIMEOUT,
    headers: dict | None = None,
) -> object | None:
    """GET and parse JSON, throttled per host, with backoff and caching.

    Returns the parsed JSON value, or None if the host keeps failing.
    """
    key = _cache_key(url, params)
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < cache_ttl:
        try:
            return json.loads(hit[1])
        except Exception:
            pass  # corrupt cache entry — fall through and re-fetch

    _throttle(_host(key), min_interval)

    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json, text/plain, */*"}
    if headers:
        hdrs.update(headers)

    attempt = 0
    while attempt < 3:
        try:
            r = requests.get(url, params=params, headers=hdrs, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                attempt += 1
                time.sleep(2 ** attempt)  # 2s, 4s, 8s
                continue
            if r.status_code != 200:
                return None
            _cache[key] = (time.time(), r.text)
            try:
                return r.json()
            except Exception:
                return None
        except requests.RequestException:
            attempt += 1
            time.sleep(2 ** attempt)
    return None


def robots_allows(url: str) -> bool:
    """Best-effort robots.txt check. Returns True if fetching is allowed or no
    robots.txt exists; False if a matching Disallow rule blocks the path."""
    try:
        from urllib.parse import urlparse

        parts = urlparse(url)
        base = f"{parts.scheme}://{parts.netloc}"
        txt = get_text(f"{base}/robots.txt", timeout=10, cache_ttl=3600)
        if not txt:
            return True
        disallows: list[str] = []
        in_block = False
        for raw in txt.splitlines():
            line = raw.strip()
            if line.lower().startswith("user-agent:"):
                ua = line.split(":", 1)[1].strip()
                in_block = ua == "*" or ua.lower() == APP_NAME
                continue
            if not in_block:
                continue
            if line.lower().startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    disallows.append(path)
        path = parts.path or "/"
        for d in disallows:
            if d == "/" or (d and path.startswith(d)):
                return False
        return True
    except Exception:
        return True  # could not check — never block the user on a parser bug


def get_text(
    url: str,
    params: dict | None = None,
    *,
    min_interval: float = DEFAULT_MIN_INTERVAL,
    cache_ttl: float = DEFAULT_CACHE_TTL,
    timeout: int = DEFAULT_TIMEOUT,
    headers: dict | None = None,
) -> str | None:
    """GET raw text, throttled per host, with backoff and caching.

    Returns the response body, or None on persistent failure.
    """
    key = _cache_key(url, params)
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < cache_ttl:
        return hit[1]

    _throttle(_host(key), min_interval)

    hdrs = {"User-Agent": USER_AGENT, "Accept": "text/html, application/xml, */*"}
    if headers:
        hdrs.update(headers)

    attempt = 0
    while attempt < 3:
        try:
            r = requests.get(url, params=params, headers=hdrs, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                attempt += 1
                time.sleep(2 ** attempt)
                continue
            if r.status_code != 200:
                return None
            _cache[key] = (time.time(), r.text)
            return r.text
        except requests.RequestException:
            attempt += 1
            time.sleep(2 ** attempt)
    return None
