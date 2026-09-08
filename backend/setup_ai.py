"""Offer and install the optional local AI (Ollama) from a terminal.

The installer scripts call this during a first install, so the offer arrives
once, up front, instead of being something you have to go and find in Settings
later. It drives the very same `ollama_setup` code the Settings button drives --
one install path, not two that can drift apart.

    python -m backend.setup_ai            # explain, ask, then install
    python -m backend.setup_ai --yes      # take the recommendation, no prompt
    python -m backend.setup_ai --model llama3.2:3b

Exits 0 whether the user says yes, says no, or the install fails: the app works
without the local AI, so nothing here should ever stop a setup from finishing.
"""
from __future__ import annotations

import argparse
import sys
import textwrap
import time
from pathlib import Path

from dotenv import load_dotenv

# .env holds OLLAMA_MODEL/OLLAMA_HOST, which decide what counts as "already
# installed". Load it before the modules that read it.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from . import hardware, ollama_client, ollama_setup  # noqa: E402

WIDTH = 72


def _say(text: str = "", indent: str = "   ") -> None:
    if not text:
        print(flush=True)
        return
    for line in textwrap.wrap(text, width=WIDTH, subsequent_indent=indent):
        print(f"{indent}{line}" if not line.startswith(indent) else line, flush=True)


def _already_on() -> bool:
    """True when a previous run left a working model in place, so a re-run of
    setup does not re-ask a question that is already answered."""
    st = ollama_client.status()
    return bool(st.get("enabled") and st.get("reachable") and st.get("model_ready"))


def _describe(rec: dict) -> None:
    sp = rec["specs"]
    ram = f"{sp['ram_total_gb']:.0f} GB RAM" if sp["ram_total_gb"] else "unknown RAM"
    parts = [p for p in (sp["os"], ram, sp["gpu"]) if p]
    _say(f"Your machine: {', '.join(parts)}")
    _say()
    model = rec["recommended"]
    _say(f"Recommended:  {model['label']}  (~{model['size_gb']} GB download)")
    _say(model["note"])
    _say()
    _say(rec["reason"])
    if rec["warning"]:
        _say()
        _say(rec["warning"])


class _Reporter:
    """Prints each step once as it changes, plus a live percentage for the long
    model download. A terminal that scrolls a hundred near-identical progress
    lines is harder to read than one that rewrites a single line."""

    def __init__(self) -> None:
        self._step: dict[str, str] = {}
        self._detail: dict[str, str] = {}
        self._open = False  # a carriage-return line is awaiting its newline

    def update(self, steps: list[dict]) -> None:
        for step in steps:
            status = step["status"]
            if status == "pending":
                continue
            key, detail = step["key"], step.get("detail", "")
            if key not in self._step:
                self._close()
                print(f"   - {step['label']}...", flush=True)
                self._step[key] = "running"
            if status != self._step[key]:
                self._step[key] = status
                self._close()
                suffix = f" ({detail})" if detail else ""
                word = {
                    "done": "done",
                    "error": "FAILED",
                    "manual": "needs one manual step",
                }.get(status)
                if word:
                    print(f"     {word}{suffix}", flush=True)
            elif status == "running" and detail and self._detail.get(key) != detail:
                self._detail[key] = detail
                print(f"\r     {detail[:WIDTH]:<{WIDTH}}", end="", flush=True)
                self._open = True

    def _close(self) -> None:
        if self._open:
            print(flush=True)
            self._open = False

    finish = _close


def _install(model: str) -> str:
    """Run the install to completion, printing progress. Returns the end state."""
    ollama_setup.start_setup(model)
    reporter = _Reporter()
    while True:
        status = ollama_setup.status()
        reporter.update(status["steps"])
        if not ollama_setup.is_running():
            reporter.update(ollama_setup.status()["steps"])  # catch the last flip
            break
        time.sleep(0.5)
    reporter.finish()
    return ollama_setup.status()["state"]


def _ask(question: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        answer = input(f"   {question} {suffix} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(flush=True)
        return False
    print(flush=True)
    if not answer:
        return default_yes
    return answer[0] == "y"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set up the optional local AI.")
    parser.add_argument("--yes", action="store_true",
                        help="install the recommended model without asking")
    parser.add_argument("--model", default="",
                        help="install this model instead of the recommended one")
    args = parser.parse_args(argv)

    print(flush=True)
    print("   Optional: free local AI", flush=True)
    print("   " + "-" * 23, flush=True)
    _say("This is a small AI model that runs on your own computer. It makes "
         "reading your resume and wording your tailored CVs noticeably better. "
         "It is free, it needs no account, and nothing you write leaves your "
         "machine. The app works fully without it.")
    _say()

    if _already_on():
        _say("Already set up and switched on. Skipping.")
        return 0

    try:
        rec = hardware.recommend()
    except Exception as exc:  # never let a hardware probe stop a setup
        _say(f"Could not check this machine ({exc}). You can set the local AI "
             f"up later from Settings inside the app.")
        return 0

    _describe(rec)
    _say()

    if not args.yes and not sys.stdin.isatty():
        # No terminal to ask through -- an automated run, or a pipe. Say so
        # rather than treating the silence as a "no" the user never gave.
        _say("Not running in a terminal, so skipping the question. Turn the "
             "local AI on any time from Settings inside the app.")
        return 0

    if not args.yes and not _ask("Install it now? It downloads in the background."):
        _say("Skipped. You can turn it on any time from Settings inside the app.")
        return 0

    model = args.model.strip() or rec["recommended"]["name"]
    _say(f"Installing {model}. This can take several minutes.")
    print(flush=True)

    try:
        state = _install(model)
        message = ollama_setup.status().get("message", "")
    except Exception as exc:
        state, message = "error", str(exc)

    print(flush=True)
    if state == "done":
        _say("Local AI is installed and switched on.")
    elif state == "manual":
        _say(message or "Ollama needs to be installed by hand first.")
    else:
        _say(f"The local AI did not finish installing: {message}")
        _say("This does not affect anything else -- the app works without it, "
             "and you can retry from Settings inside the app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
