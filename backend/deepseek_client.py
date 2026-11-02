"""DeepSeek — or any OpenAI-compatible chat API — as an alternative to Ollama.

Paid but cheap, and works on any machine without a big local download. The user
can bring their own key, and optionally their own base URL + model name
(OpenRouter, Groq, a self-hosted vLLM endpoint, and so on).

The API key is NOT stored here. Electron keeps it in the OS keychain/DPAPI and
passes it to the backend as the in-memory environment variable AI_API_KEY at
startup. It is never logged, echoed, or written to a file.
"""
from __future__ import annotations

import json
import os

import requests


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def base_url() -> str:
    return _env("AI_BASE_URL", "https://api.deepseek.com").rstrip("/")


def model() -> str:
    return _env("AI_MODEL", "deepseek-chat")


def api_key() -> str:
    return _env("AI_API_KEY", "")


def preflight() -> str | None:
    """Return an error string if generation cannot run, else None."""
    if not api_key():
        return "no API key set (add one in Settings → AI model)"
    return None


def _chat(payload: dict, timeout: int) -> tuple[dict | None, str | None]:
    headers = {
        "Authorization": f"Bearer {api_key()}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(
            f"{base_url()}/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
    except requests.Timeout:
        return None, f"the AI provider timed out after {timeout}s"
    except requests.RequestException as exc:
        return None, f"could not reach the AI provider: {exc}"
    if r.status_code != 200:
        detail = (r.text or "").strip()[:200]
        return None, f"the AI provider returned {r.status_code}: {detail}"
    try:
        return r.json(), None
    except ValueError:
        return None, "the AI provider returned a response that was not JSON"


def _messages(prompt: str, system: str | None) -> list[dict]:
    msgs: list[dict] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


def _content(data: dict | None) -> tuple[str, str | None]:
    try:
        text = (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return "", "the AI provider returned an unexpected response shape"
    return text, None


def generate(
    prompt: str, *, system: str | None = None, temperature: float = 0.2,
    timeout: int | None = None,
) -> tuple[str | None, str | None]:
    """Single-shot generation. Returns (text, error); exactly one is set."""
    err = preflight()
    if err:
        return None, err
    payload = {
        "model": model(),
        "messages": _messages(prompt, system),
        "temperature": temperature,
        "stream": False,
    }
    data, err = _chat(payload, timeout or 120)
    if err:
        return None, err
    return _content(data)


def generate_json(
    prompt: str, *, system: str | None = None, timeout: int | None = None,
) -> tuple[dict | list | None, str | None]:
    """Generation that asks for JSON and parses it. Returns (data, error)."""
    err = preflight()
    if err:
        return None, err
    payload = {
        "model": model(),
        "messages": _messages(prompt, system),
        "temperature": 0.1,
        "stream": False,
    }
    data, err = _chat(payload, timeout or 300)
    if err:
        return None, err
    text, err = _content(data)
    if err:
        return None, err
    if not text:
        return None, "the AI provider returned an empty response"
    # Tolerate markdown code fences some providers wrap JSON in.
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, f"the AI provider returned invalid JSON: {exc}"
