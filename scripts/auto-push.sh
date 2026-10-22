#!/bin/bash
# Commit whatever changed in this folder and push it to GitHub.
#
# Run by the launchd agent that "Enable auto-push.command" installs, every 30
# minutes. Safe to run by hand at any time.
#
# What it will not do: it never deletes anything, never force-pushes, and never
# touches a file .gitignore excludes -- which is what keeps master_profile.yaml,
# your .env, your job database and PROGRESS.md off GitHub. If the working tree
# is clean it exits without making an empty commit.

set -u

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$HOME/.career-copilot/logs"
LOG="$LOG_DIR/auto-push.log"

mkdir -p "$LOG_DIR"
# Keep the log from growing without bound.
if [ -f "$LOG" ] && [ "$(wc -c <"$LOG")" -gt 1000000 ]; then
  mv "$LOG" "$LOG.1"
fi

say() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"; }

cd "$REPO_DIR" || { say "FATAL: cannot enter $REPO_DIR"; exit 1; }

# Homebrew's git/gh are not on the PATH a launchd job inherits.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

command -v git >/dev/null 2>&1 || { say "FATAL: git not found"; exit 1; }

if [ ! -d .git ]; then
  say "FATAL: $REPO_DIR is not a git repository. Run \"Enable auto-push.command\" once."
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  say "FATAL: no 'origin' remote. Run \"Enable auto-push.command\" once."
  exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"

# ---------------------------------------------------------------------------
# Commit anything new. `git add -A` stages tracked changes, new files and
# removals, but .gitignore still decides what is eligible -- so the personal
# files stay out.
# ---------------------------------------------------------------------------
git add -A
if git diff --cached --quiet; then
  say "nothing to commit"
else
  count="$(git diff --cached --name-only | wc -l | tr -d ' ')"
  summary="$(git diff --cached --name-only | head -3 | tr '\n' ' ')"
  git commit -q -m "Auto-commit: $count file(s) changed" \
    -m "Changed: ${summary}$([ "$count" -gt 3 ] && echo '...')" \
    >>"$LOG" 2>&1
  say "committed $count file(s)"
fi

# ---------------------------------------------------------------------------
# Push. Nothing to push is the normal, quiet case.
# ---------------------------------------------------------------------------
# How far ahead of the remote we are. If git has no local record of
# origin/<branch> -- a fresh clone-less repo, or a ref that was never fetched --
# the count cannot be computed, and treating that as "0 commits to push" would
# mean this script silently never pushed anything. So: no ref, always push.
if git rev-parse --verify --quiet "refs/remotes/origin/$branch" >/dev/null; then
  ahead="$(git rev-list --count "origin/$branch..$branch" 2>/dev/null || echo 1)"
  if [ "$ahead" = "0" ]; then
    say "nothing to push"
    exit 0
  fi
else
  ahead="unknown number of"
  say "no local record of origin/$branch yet -- pushing to establish it"
fi

say "pushing $ahead commit(s) to origin/$branch"
if git push origin "$branch" >>"$LOG" 2>&1; then
  say "pushed OK"
else
  say "PUSH FAILED -- see above. If it mentions authentication, run: gh auth login"
  exit 1
fi
