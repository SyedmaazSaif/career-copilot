"""One-click setup for the optional local AI (Ollama).

Runs in a background thread and reports each step so the UI can show progress:
  check -> install (Windows) -> start -> pull model -> enable.

Only downloads from the official Ollama site. On macOS/Linux, auto-install is not
attempted; the flow returns a "manual" step with the download link. No paid API
is ever involved.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import requests

from . import hardware, ollama_client

OLLAMA_WIN_INSTALLER = "https://ollama.com/download/OllamaSetup.exe"
DOWNLOAD_PAGE = "https://ollama.com/download"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

_lock = threading.Lock()
_thread: threading.Thread | None = None
# The model this run is installing. Set when setup starts so the pull, the
# "already downloaded" check and the .env write all agree on one name.
_chosen_model: str = ""

# Shared, pollable status.
_status: dict = {
    "state": "idle",  # idle | running | done | error | manual
    "message": "",
    "model": "",  # the model this run is installing
    "steps": [],  # [{key,label,status,detail}]
}

_STEP_DEFS = [
    ("check", "Check for Ollama"),
    ("install", "Install Ollama"),
    ("start", "Start the AI service"),
    ("pull", "Download the AI model"),
    ("enable", "Turn it on"),
]


def status() -> dict:
    return _status


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()


def _reset_steps():
    _status["steps"] = [
        {"key": k, "label": lbl, "status": "pending", "detail": ""}
        for k, lbl in _STEP_DEFS
    ]


def _set(key: str, status_: str, detail: str = ""):
    for s in _status["steps"]:
        if s["key"] == key:
            s["status"] = status_
            if detail:
                s["detail"] = detail
            break


def start_setup(model: str | None = None) -> dict:
    """Install Ollama and download `model`. With no model given, the one this
    machine can actually run, so we never install something that will page to
    disk and time out on every request."""
    global _thread, _chosen_model
    with _lock:
        if is_running():
            return _status
        chosen = (model or "").strip() or hardware.recommend()["recommended"]["name"]
        _chosen_model = chosen
        _reset_steps()
        _status["state"] = "running"
        _status["message"] = ""
        _status["model"] = chosen
        _thread = threading.Thread(target=_run, daemon=True)
        _thread.start()
    return _status


def _reachable() -> bool:
    try:
        r = requests.get(f"{ollama_client.host()}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _model_present() -> bool:
    want = _chosen_model or ollama_client.model()
    try:
        r = requests.get(f"{ollama_client.host()}/api/tags", timeout=3)
        names = [m.get("name", "") for m in r.json().get("models", [])]
        if ":" in want:
            return want in names
        return any(n.split(":")[0] == want for n in names)
    except Exception:
        return False


def _run():
    try:
        # 1. Check
        _set("check", "running")
        installed = _reachable() or shutil.which("ollama") is not None
        _set("check", "done", "already installed" if installed else "not found")

        # 2. Install (Windows only, if needed)
        if installed:
            _set("install", "done", "skipped")
        elif platform.system() == "Windows":
            _set("install", "running", "downloading installer…")
            exe = _download_installer()
            _set("install", "running", "running installer…")
            subprocess.run([str(exe), "/VERYSILENT", "/NORESTART"], check=False)
            _set("install", "done", "installed")
        else:
            _set("install", "manual", f"install Ollama from {DOWNLOAD_PAGE}, then retry")
            _status["state"] = "manual"
            _status["message"] = (
                f"Automatic install is Windows-only. Install Ollama from "
                f"{DOWNLOAD_PAGE}, then click Set up again."
            )
            return

        # 3. Start / wait for service
        _set("start", "running", "waiting for the service…")
        ok = False
        for _ in range(40):  # up to ~40s
            if _reachable():
                ok = True
                break
            time.sleep(1)
        if not ok:
            _set("start", "error", "service did not start")
            raise RuntimeError("Ollama installed but the service did not start in time")
        _set("start", "done", "running")

        # 4. Pull the model (streamed progress)
        _set("pull", "running", "starting download…")
        if _model_present():
            _set("pull", "done", "already downloaded")
        else:
            _pull_model()
            _set("pull", "done", "downloaded")

        # 5. Enable
        _set("enable", "running")
        _enable_in_env()
        _set("enable", "done", "on")

        _status["state"] = "done"
        _status["message"] = "Local AI is ready."
    except Exception as exc:
        _status["state"] = "error"
        _status["message"] = str(exc)[:500]


def _download_installer() -> Path:
    dest = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
    with requests.get(OLLAMA_WIN_INSTALLER, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return dest


def _pull_model():
    model = _chosen_model or ollama_client.model()
    with requests.post(
        f"{ollama_client.host()}/api/pull",
        json={"name": model, "stream": True},
        stream=True,
        timeout=None,
    ) as r:
        r.raise_for_status()
        import json as _json

        for line in r.iter_lines():
            if not line:
                continue
            try:
                msg = _json.loads(line)
            except Exception:
                continue
            st = msg.get("status", "")
            total = msg.get("total")
            completed = msg.get("completed")
            if total and completed:
                pct = int(completed * 100 / total)
                _set("pull", "running", f"{st} {pct}%")
            elif st:
                _set("pull", "running", st)
            if msg.get("error"):
                raise RuntimeError(msg["error"])


def _enable_in_env():
    """Turn the local AI on and pin the model we just installed. Writing the
    model matters: without it the app would keep using whatever OLLAMA_MODEL
    said before, which is how it ends up pointing at a model that is not there
    or does not fit."""
    values = {
        "OLLAMA_ENABLED": "true",
        "OLLAMA_MODEL": _chosen_model or ollama_client.model(),
    }
    # Update the running process immediately…
    os.environ.update(values)
    # …and persist to .env so it survives a restart.
    lines = []
    seen = set()
    if ENV_PATH.exists():
        for ln in ENV_PATH.read_text(encoding="utf-8").splitlines():
            key = ln.split("=", 1)[0].strip()
            if key in values:
                lines.append(f"{key}={values[key]}")
                seen.add(key)
            else:
                lines.append(ln)
    for key, value in values.items():
        if key not in seen:
            lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
