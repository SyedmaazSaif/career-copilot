#!/bin/bash
# Double-click this once. After that, every change in this folder is committed
# and pushed to GitHub on its own, every 30 minutes, with nothing to click.
#
# It does three things:
#   1. makes sure this folder is a git repo pointed at your GitHub repo
#   2. signs you in to GitHub if you are not already (browser, no token to copy)
#   3. installs a background job that commits and pushes every 30 minutes
#
# Nothing is ever deleted, nothing is force-pushed, and .gitignore still keeps
# your personal files -- master_profile.yaml, .env, your job database -- off
# GitHub entirely.
#
# To stop it later, run this file again and choose to turn it off.

set -u
cd "$(dirname "$0")" || exit 1

REPO_DIR="$PWD"
REPO_URL="${CAREER_COPILOT_REPO_URL:-https://github.com/SyedmaazSaif/career-copilot.git}"
LABEL="com.syedmaazsaif.career-copilot.autopush"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
INTERVAL=1800  # seconds — every 30 minutes

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

say()  { printf '%s\n' "$*"; }
die()  { printf '\n   %s\n\n' "$*"; read -r -p "Press Return to close." _; exit 1; }

say "====================================================="
say "   career-copilot  -  automatic GitHub push"
say "====================================================="
say ""

# ---------------------------------------------------------------------------
# Turning it off
# ---------------------------------------------------------------------------
if [ -f "$PLIST" ]; then
  say "Automatic push is currently ON."
  read -r -p "Turn it OFF? [y/N] " answer
  case "$answer" in
    [Yy]*)
      launchctl unload "$PLIST" 2>/dev/null
      rm -f "$PLIST"
      say ""
      say "   Turned off. Your commits and your files are untouched."
      say ""
      read -r -p "Press Return to close." _
      exit 0
      ;;
    *) say "   Leaving it on. Re-checking the setup below." ;;
  esac
fi

# ---------------------------------------------------------------------------
# 1. git repo + remote
# ---------------------------------------------------------------------------
say "[1/3] Checking the repository..."
command -v git >/dev/null 2>&1 || die "git is missing. Install Xcode command line tools: xcode-select --install"

if [ ! -d .git ]; then
  say "      Not a git repository yet -- setting one up."
  git init -q
  git branch -M main
fi

if git remote get-url origin >/dev/null 2>&1; then
  say "      Remote: $(git remote get-url origin)"
else
  git remote add origin "$REPO_URL"
  say "      Remote added: $REPO_URL"
fi

# ---------------------------------------------------------------------------
# 2. GitHub sign-in
# ---------------------------------------------------------------------------
say "[2/3] Checking your GitHub sign-in..."
if ! command -v gh >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    say "      Installing the GitHub CLI (one time)..."
    brew install gh || die "Could not install the GitHub CLI. Install it from https://cli.github.com and run this again."
  else
    die "The GitHub CLI is needed and Homebrew is not installed. Get it from https://cli.github.com, then run this again."
  fi
fi

if gh auth status >/dev/null 2>&1; then
  say "      Already signed in."
else
  say "      Opening your browser to sign in to GitHub..."
  say "      (GitHub stopped accepting account passwords for git in 2021, which"
  say "       is why this uses a browser sign-in instead.)"
  gh auth login --hostname github.com --git-protocol https --web \
    || die "Sign-in did not complete. Run this file again when you are ready."
fi
gh auth setup-git >/dev/null 2>&1

# ---------------------------------------------------------------------------
# 3. the background job
# ---------------------------------------------------------------------------
say "[3/3] Installing the background job..."
chmod +x "$REPO_DIR/scripts/auto-push.sh" 2>/dev/null

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO_DIR/scripts/auto-push.sh</string>
  </array>
  <key>StartInterval</key><integer>$INTERVAL</integer>
  <!-- Run once at login too, so a machine that was asleep catches up. -->
  <key>RunAtLoad</key><true/>
  <key>StandardErrorPath</key><string>$HOME/.career-copilot/logs/auto-push.err</string>
</dict>
</plist>
PLISTEOF

launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST" || die "Could not start the background job."

say ""
say "   Automatic push is ON."
say ""
say "   Every 30 minutes, anything that changed in this folder is committed"
say "   and pushed to GitHub. Your personal files stay out of it -- .gitignore"
say "   still applies."
say ""
say "   Log:  ~/.career-copilot/logs/auto-push.log"
say "   Off:  double-click this file again and answer y"
say ""
say "   Running it once now so you can see it work..."
say ""
bash "$REPO_DIR/scripts/auto-push.sh"
tail -5 "$HOME/.career-copilot/logs/auto-push.log" 2>/dev/null

say ""
read -r -p "Press Return to close." _
