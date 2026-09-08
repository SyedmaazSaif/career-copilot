#!/bin/bash
# career-copilot one-line installer for macOS.
#
#   curl -fsSL https://raw.githubusercontent.com/SyedmaazSaif/career-copilot/main/install-macos.sh | bash
#
# Downloads the app, installs everything it needs, offers the optional local
# AI, and starts it. Nothing here needs git, Homebrew or a developer account.
#
# Why a pasted command rather than a file to double-click: macOS quarantines
# every file a browser downloads, and Gatekeeper then blocks unsigned scripts
# with "cannot be opened" or "will damage your computer". Code that arrives
# through a pipe is never quarantined, so this route simply has no wall to
# climb. Signing and notarising a real .app would remove the wall properly;
# that needs a paid Apple Developer account.

set -u

REPO="${CAREER_COPILOT_REPO:-SyedmaazSaif/career-copilot}"
BRANCH="${CAREER_COPILOT_BRANCH:-main}"
DEST="${CAREER_COPILOT_DIR:-$HOME/career-copilot}"
ZIP_URL="https://github.com/${REPO}/archive/refs/heads/${BRANCH}.zip"

say() { printf '%s\n' "$*"; }
die() { printf '\nInstall stopped: %s\n\n' "$*"; exit 1; }

say "====================================================="
say "   career-copilot  -  installer (macOS)"
say "====================================================="
say "Installing to: $DEST"
say ""

command -v curl >/dev/null 2>&1 || die "curl is missing, which should not happen on macOS."

# ---------------------------------------------------------------------------
# Download and unpack the app.
# ---------------------------------------------------------------------------
work="$(mktemp -d)" || die "Could not create a temporary folder."
trap 'rm -rf "$work"' EXIT

say "[1/3] Downloading career-copilot..."
curl -fSL --retry 3 -o "$work/app.zip" "$ZIP_URL" \
  || die "Download failed. Check your internet connection and try again."

say "[2/3] Unpacking..."
# ditto, not unzip: it keeps the executable bit on setup.command.
ditto -x -k "$work/app.zip" "$work/unpacked" || die "Could not unpack the download."
src="$(find "$work/unpacked" -maxdepth 1 -type d -name '*career-copilot*' | head -1)"
[ -n "$src" ] || die "The download did not contain the app."

if [ -d "$DEST" ]; then
  # Keep the things that are the user's, not the app's: their profile database,
  # their settings, and the CVs already generated. Reinstalling must never be
  # the reason someone loses their job search.
  say "      An existing install is here already -- updating it, keeping your data."
  backup="$(mktemp -d)"
  for keep in backend/data .env master_profile.yaml applications; do
    [ -e "$DEST/$keep" ] && { mkdir -p "$backup/$(dirname "$keep")"; cp -R "$DEST/$keep" "$backup/$keep"; }
  done
  # node_modules and the virtualenv are large and would be rebuilt identically.
  # Move them into the new copy rather than making the user download them twice.
  for reuse in node_modules backend/.venv; do
    [ -d "$DEST/$reuse" ] && { mkdir -p "$src/$(dirname "$reuse")"; mv "$DEST/$reuse" "$src/$reuse"; }
  done
  rm -rf "$DEST"
  mv "$src" "$DEST" || die "Could not write to $DEST."
  for keep in backend/data .env master_profile.yaml applications; do
    [ -e "$backup/$keep" ] && { mkdir -p "$DEST/$(dirname "$keep")"; cp -R "$backup/$keep" "$DEST/$keep"; }
  done
  rm -rf "$backup"
else
  mkdir -p "$(dirname "$DEST")"
  mv "$src" "$DEST" || die "Could not write to $DEST."
fi

# Nothing that arrived through this pipe is quarantined, but be explicit: it
# costs nothing and it guarantees the launcher opens on a double-click.
xattr -dr com.apple.quarantine "$DEST" >/dev/null 2>&1 || true
chmod +x "$DEST/setup.command" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Hand over to the setup script, which does the actual work.
# ---------------------------------------------------------------------------
say "[3/3] Running setup..."
cd "$DEST" || die "Could not open $DEST."
# When this script arrives through `curl | bash`, stdin is the pipe, and it is
# already at end-of-file. Setup asks a question (the optional local AI), so hand
# it the terminal instead -- otherwise that question answers itself with silence.
if [ -e /dev/tty ]; then
  exec bash ./setup.command < /dev/tty
else
  exec bash ./setup.command
fi
