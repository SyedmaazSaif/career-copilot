"""Editable related-title expansion.

The map lives in title_expansions.json (a data file, not code) so users can add
their own profession's related titles without touching the app. Keys and values
are lowercase; matching is case-insensitive.
"""
from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).with_name("title_expansions.json")


def load_expansions() -> dict[str, list[str]]:
    try:
        data = json.loads(_PATH.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def expand_titles(titles: list[str]) -> list[str]:
    """Return the titles plus their related titles, deduped, order preserved."""
    exp = load_expansions()
    out: list[str] = []
    seen: set[str] = set()

    def add(t: str) -> None:
        key = (t or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append((t or "").strip())

    for t in titles:
        if not t:
            continue
        add(t)
        for rel in exp.get((t or "").strip().lower(), []):
            add(rel)
    return out
