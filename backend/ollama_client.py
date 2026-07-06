"""Optional local AI via Ollama. Free, on-device, no API key.

Everything here degrades gracefully: if Ollama is not installed or not running,
`available()` is False and callers fall back to deterministic logic. No paid API
is ever called.
"""
from __future__ import annotations

import json
import os

import requests

HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")


def enabled() -> bool:
    return os.getenv("OLLAMA_ENABLED", "false").lower() == "true"


def available() -> tuple[bool, list[str]]:
    """Return (is_reachable, installed_model_names). Never raises."""
    if not enabled():
        return False, []
    try:
        r = requests.get(f"{HOST}/api/tags", timeout=2)
        if r.status_code != 200:
            return False, []
        models = [m.get("name", "") for m in r.json().get("models", [])]
        return True, models
    except Exception:
        return False, []


def status() -> dict:
    ok, models = available()
    return {
        "enabled": enabled(),
        "reachable": ok,
        "host": HOST,
        "model": MODEL,
        "models": models,
        "model_ready": ok and any(m.split(":")[0] == MODEL.split(":")[0] for m in models),
    }


def generate(prompt: str, *, system: str | None = None, temperature: float = 0.2,
             timeout: int = 120) -> str | None:
    """Single-shot generation. Returns text, or None if Ollama is unavailable."""
    ok, _ = available()
    if not ok:
        return None
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system
    try:
        r = requests.post(f"{HOST}/api/generate", json=payload, timeout=timeout)
        if r.status_code != 200:
            return None
        return (r.json().get("response") or "").strip()
    except Exception:
        return None


def generate_json(prompt: str, *, system: str | None = None,
                  timeout: int = 180) -> dict | list | None:
    """Generation that asks for JSON and parses it. Returns None on any failure
    so callers can fall back to deterministic logic."""
    ok, _ = available()
    if not ok:
        return None
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }
    if system:
        payload["system"] = system
    try:
        r = requests.post(f"{HOST}/api/generate", json=payload, timeout=timeout)
        if r.status_code != 200:
            return None
        text = (r.json().get("response") or "").strip()
        return json.loads(text) if text else None
    except Exception:
        return None
