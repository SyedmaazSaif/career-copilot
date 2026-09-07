"""Optional local AI via Ollama. Free, on-device, no API key.

Everything here degrades gracefully: if Ollama is not installed or not running,
`available()` is False and callers fall back to deterministic logic. No paid API
is ever called.

Generation returns a `(value, error)` pair rather than a bare None, so callers
can tell "the local model is switched off" apart from "the local model timed
out" and say so in the UI instead of silently producing a worse result.
"""
from __future__ import annotations

import json
import os

import requests


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


# Read lazily: main.py loads .env after this module is first imported.
def host() -> str:
    return _env("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def model() -> str:
    return _env("OLLAMA_MODEL", "llama3.2:1b")


def num_ctx() -> int:
    """Context window. Ollama defaults to 4096, which a resume plus the schema
    plus the JSON answer overflows silently -- so we always set it."""
    return _env_int("OLLAMA_NUM_CTX", 8192)


# Back-compat aliases; ollama_setup.py reads these.
HOST = host()
MODEL = model()


def enabled() -> bool:
    return _env("OLLAMA_ENABLED", "false").lower() == "true"


def available() -> tuple[bool, list[str]]:
    """Return (is_reachable, installed_model_names). Never raises."""
    if not enabled():
        return False, []
    try:
        r = requests.get(f"{host()}/api/tags", timeout=2)
        if r.status_code != 200:
            return False, []
        models = [m.get("name", "") for m in r.json().get("models", [])]
        return True, models
    except Exception:
        return False, []


def _model_installed(models: list[str]) -> bool:
    want = model()
    # "llama3.2:1b" matches exactly; "llama3.2" matches any tag of that base.
    if ":" in want:
        return want in models
    return any(m.split(":")[0] == want for m in models)


def status() -> dict:
    ok, models = available()
    return {
        "enabled": enabled(),
        "reachable": ok,
        "host": host(),
        "model": model(),
        "models": models,
        "model_ready": ok and _model_installed(models),
    }


def preflight() -> str | None:
    """Return an error string if generation cannot run, else None."""
    if not enabled():
        return "local AI is switched off (set OLLAMA_ENABLED=true)"
    ok, models = available()
    if not ok:
        return f"Ollama is not reachable at {host()} (is it running?)"
    if not _model_installed(models):
        installed = ", ".join(models) or "none"
        return f"model '{model()}' is not installed (installed: {installed})"
    return None


def _post(payload: dict, timeout: int) -> tuple[dict | None, str | None]:
    try:
        r = requests.post(f"{host()}/api/generate", json=payload, timeout=timeout)
    except requests.Timeout:
        return None, (
            f"the local model timed out after {timeout}s -- it is too slow on this "
            "machine for this request (try a smaller OLLAMA_MODEL)"
        )
    except requests.RequestException as exc:
        return None, f"could not reach Ollama: {exc}"
    if r.status_code != 200:
        detail = (r.text or "").strip()[:200]
        return None, f"Ollama returned {r.status_code}: {detail}"
    try:
        return r.json(), None
    except ValueError:
        return None, "Ollama returned a response that was not JSON"


def generate(prompt: str, *, system: str | None = None, temperature: float = 0.2,
             timeout: int | None = None) -> tuple[str | None, str | None]:
    """Single-shot generation. Returns (text, error); exactly one is set."""
    err = preflight()
    if err:
        return None, err
    payload = {
        "model": model(),
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": num_ctx()},
    }
    if system:
        payload["system"] = system
    data, err = _post(payload, timeout or _env_int("OLLAMA_TIMEOUT", 120))
    if err:
        return None, err
    return (data.get("response") or "").strip(), None


def generate_json(prompt: str, *, system: str | None = None,
                  timeout: int | None = None,
                  ) -> tuple[dict | list | None, str | None]:
    """Generation that asks for JSON and parses it. Returns (data, error) so the
    caller can report why it fell back instead of failing silently."""
    err = preflight()
    if err:
        return None, err
    payload = {
        "model": model(),
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_ctx": num_ctx()},
    }
    if system:
        payload["system"] = system
    data, err = _post(payload, timeout or _env_int("OLLAMA_JSON_TIMEOUT", 300))
    if err:
        return None, err
    text = (data.get("response") or "").strip()
    if not text:
        return None, "the local model returned an empty response"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, f"the local model returned invalid JSON: {exc}"
