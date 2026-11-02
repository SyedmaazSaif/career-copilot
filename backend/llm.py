"""Unified AI entry point.

Callers use this module instead of importing ollama_client directly, so the
provider can be switched in Settings without touching resume/CV code:

- `ollama`  -> local Ollama (free, on-device, no key)
- anything else (`deepseek` / `custom`) -> an OpenAI-compatible API
"""
from __future__ import annotations

import os

from . import deepseek_client, ollama_client


def provider() -> str:
    return (os.getenv("AI_PROVIDER", "ollama") or "ollama").strip().lower()


def _client():
    return ollama_client if provider() == "ollama" else deepseek_client


def status() -> dict:
    p = provider()
    if p == "ollama":
        return {"provider": p, **ollama_client.status()}
    return {
        "provider": p,
        "enabled": bool(deepseek_client.api_key()),
        "reachable": bool(deepseek_client.api_key()),
        "model": deepseek_client.model(),
        "base_url": deepseek_client.base_url(),
        "has_key": bool(deepseek_client.api_key()),
    }


def preflight() -> str | None:
    return _client().preflight()


def generate(prompt: str, **kwargs):
    return _client().generate(prompt, **kwargs)


def generate_json(prompt: str, **kwargs):
    return _client().generate_json(prompt, **kwargs)
