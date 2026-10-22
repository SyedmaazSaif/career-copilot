"""Run child processes without flashing a console window.

On Windows, a console program started from a GUI process gets a brand new
console window of its own. The backend shells out to `powershell` and
`nvidia-smi` while it works out what local model this machine can run, so
without this wrapper the app blinks a PowerShell window onto the desktop
every time it checks the hardware -- which looks like something went wrong.

CREATE_NO_WINDOW suppresses that console; STARTF_USESHOWWINDOW/SW_HIDE covers
the older shells that ignore the flag. On macOS and Linux there is no console
to create, so both helpers are plain passthroughs to `subprocess`.

Use `proc.run` / `proc.popen` anywhere the backend starts a child process.
"""
from __future__ import annotations

import subprocess
import sys

_IS_WINDOWS = sys.platform == "win32"

# Defined here as well as read from subprocess, because the constant only
# exists on Windows builds of the stdlib.
_CREATE_NO_WINDOW = 0x08000000


def _hidden(kwargs: dict) -> dict:
    """Add the flags that keep a child process off the desktop."""
    if not _IS_WINDOWS:
        return kwargs

    flags = kwargs.get("creationflags", 0)
    kwargs["creationflags"] = flags | getattr(
        subprocess, "CREATE_NO_WINDOW", _CREATE_NO_WINDOW
    )

    startupinfo = kwargs.get("startupinfo") or subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    kwargs["startupinfo"] = startupinfo
    return kwargs


def run(*args, **kwargs):
    """subprocess.run, with no console window on Windows."""
    return subprocess.run(*args, **_hidden(kwargs))


def popen(*args, **kwargs):
    """subprocess.Popen, with no console window on Windows."""
    return subprocess.Popen(*args, **_hidden(kwargs))
