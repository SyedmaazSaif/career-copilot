"""Build the downloadable installer zips for macOS and Windows.

    python mac-installer/build_zip.py

Run this after editing "Install Career Copilot.command" or install-windows.bat,
then commit the regenerated zips at the repo root.

Why zips rather than linking the scripts directly:

  * macOS -- a browser downloading a bare .command strips its executable bit,
    and Finder then refuses to run it, so the file looks broken to the user. A
    zip carries Unix permissions, so the file inside stays runnable.
  * Windows -- GitHub serves a raw .bat as text/plain, so clicking the link
    shows the source code in the browser instead of downloading it. Telling a
    non-technical user to "right-click, Save link as" is a step that loses
    people. A zip just downloads.

Getting the macOS entry right is the fiddly part, and is what most of this
script is for:

  * create_system = 3 (Unix). Archive Utility ignores permission bits entirely
    on entries claiming to come from Windows, which is what Python writes by
    default when it runs on Windows.
  * external_attr = mode << 16, with mode 0o100755 -- regular file, rwxr-xr-x.
  * LF line endings, because a CRLF shebang fails on macOS as
    "bad interpreter: /bin/bash^M".

The Windows entry wants the opposite line endings: cmd.exe is unreliable with
LF-only batch files. This is generated on Windows, so none of it can be
inherited from the filesystem; every field is set explicitly below.
"""
from __future__ import annotations

import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# A fixed timestamp keeps each zip byte-identical between rebuilds, so one only
# shows up in a diff when its contents actually changed.
TIMESTAMP = (2026, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class Target:
    output: Path
    source: Path
    entry_name: str
    mode: int          # Unix mode stored in the zip
    create_system: int  # 3 = Unix, 0 = Windows/FAT
    newline: str
    first_line: str


TARGETS = (
    Target(
        output=ROOT / "Install-Career-Copilot-Mac.zip",
        source=HERE / "Install Career Copilot.command",
        entry_name="Install Career Copilot.command",
        mode=0o100755,
        create_system=3,
        newline="\n",
        first_line="#!/bin/bash",
    ),
    Target(
        output=ROOT / "Install-Career-Copilot-Windows.zip",
        source=ROOT / "install-windows.bat",
        entry_name="Install Career Copilot.bat",
        mode=0o100644,
        create_system=0,
        newline="\r\n",
        first_line="@echo off",
    ),
)


def build(target: Target) -> None:
    body = target.source.read_text(encoding="utf-8")
    # Normalise to LF first, then to whatever this target needs. Normalise
    # rather than merely check: these files are edited on Windows.
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    if body.splitlines()[0].strip() != target.first_line:
        raise SystemExit(
            f"{target.source.name} must start with {target.first_line!r}"
        )
    if target.newline != "\n":
        body = body.replace("\n", target.newline)

    info = zipfile.ZipInfo(target.entry_name, date_time=TIMESTAMP)
    info.create_system = target.create_system
    info.external_attr = target.mode << 16
    info.compress_type = zipfile.ZIP_DEFLATED

    with zipfile.ZipFile(target.output, "w") as zf:
        zf.writestr(info, body.encode("utf-8"))


def verify(target: Target) -> None:
    """Check each zip the way the target system will read it, so a broken build
    fails here rather than on a stranger's computer."""
    with zipfile.ZipFile(target.output) as zf:
        names = zf.namelist()
        if names != [target.entry_name]:
            raise SystemExit(f"{target.output.name}: expected one entry, got {names}")
        info = zf.getinfo(target.entry_name)
        mode = info.external_attr >> 16
        content = zf.read(target.entry_name)

    problems = []
    if info.create_system != target.create_system:
        problems.append(
            f"create_system is {info.create_system}, expected {target.create_system}"
        )
    if mode != target.mode:
        problems.append(f"mode is {mode:o}, expected {target.mode:o}")
    if target.mode & 0o111 and not mode & 0o111:
        problems.append("file should be executable and is not")

    text = content.decode("utf-8")
    if target.newline == "\n":
        if "\r" in text:
            problems.append("contains CR bytes; this target needs LF endings")
    elif "\r\n" not in text:
        problems.append("missing CRLF endings; cmd.exe needs them")
    if not text.startswith(target.first_line):
        problems.append(f"does not start with {target.first_line!r}")

    if problems:
        raise SystemExit(
            f"{target.output.name} is wrong:\n  - " + "\n  - ".join(problems)
        )

    print(f"{target.output.relative_to(ROOT)}  ({target.output.stat().st_size} bytes)")
    print(f"    entry   : {target.entry_name}")
    print(f"    mode    : {stat.filemode(mode)}")
    print(f"    system  : {'Unix' if info.create_system == 3 else 'Windows'}")
    print(f"    endings : {'LF' if target.newline == chr(10) else 'CRLF'}")


if __name__ == "__main__":
    for t in TARGETS:
        build(t)
        verify(t)
