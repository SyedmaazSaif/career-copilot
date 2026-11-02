"""Write non-secret config to the git-ignored .env, and update the live process.

Secrets never go through here. The only secret (an AI API key) is held by
Electron in the OS keychain/DPAPI and passed to the backend as an in-memory
environment variable — it is never written to .env or any file.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def set_values(values: dict[str, str]) -> None:
    """Update os.environ now, and persist to .env so it survives a restart.

    Existing keys are rewritten in place; new keys are appended. The format is
    plain KEY=value, matching python-dotenv's parser.
    """
    os.environ.update(values)

    lines: list[str] = []
    seen: set[str] = set()
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
