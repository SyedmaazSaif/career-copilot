#!/bin/bash
# career-copilot setup for macOS.
#
# Double-click this file in Finder, or run it in Terminal. It installs
# everything the app needs -- including Node and Python if this Mac does not
# have them -- offers the optional local AI, and starts the app. It never sends
# you off to a website to install something by hand, and it never needs an
# administrator password: anything missing goes into ~/.career-copilot/tools,
# which your own account owns.
#
# If macOS refuses to open this file ("cannot be opened because it is from an
# unidentified developer", or "will damage your computer"), that is Gatekeeper
# reacting to a file a browser downloaded, not a problem with the file. Either
# right-click it and choose Open, or use the one-line install command in
# INSTALL.md, which sidesteps Gatekeeper entirely.

set -u
cd "$(dirname "$0")" || exit 1

TOOLS="$HOME/.career-copilot/tools"
NODE_INDEX="https://nodejs.org/dist/latest-v20.x"
# Relocatable CPython builds -- the same ones uv installs. They need no
# administrator rights, which is the whole point: an installer that stops to
# ask for a password is an installer some people never get past.
PY_API="https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"
PY_FALLBACK_TAG="20260901"
PY_FALLBACK_VER="3.12.14"
STEPS=6

say()  { printf '%s\n' "$*"; }
step() { printf '\n[%s/%s] %s\n' "$1" "$STEPS" "$2"; }
die()  { printf '\n   %s\n\n' "$*"; read -r -p "Press Return to close." _; exit 1; }

case "$(uname -m)" in
  arm64)  NODE_ARCH="darwin-arm64"; PY_ARCH="aarch64-apple-darwin" ;;
  x86_64) NODE_ARCH="darwin-x64";   PY_ARCH="x86_64-apple-darwin" ;;
  *)      die "Unsupported processor: $(uname -m). career-copilot needs an Intel or Apple Silicon Mac." ;;
esac

say "====================================================="
say "   career-copilot  -  setup (macOS)"
say "====================================================="
say "This installs everything the app needs, then starts it."
say "Leave this window open while you use the app."

# Strip the quarantine flag from this folder so the launcher created at the end
# opens on a double-click instead of hitting the Gatekeeper wall every time.
xattr -dr com.apple.quarantine . >/dev/null 2>&1 || true

mkdir -p "$TOOLS" || die "Could not create $TOOLS."
export PATH="$TOOLS/node/bin:$PATH"

# ---------------------------------------------------------------------------
# Step 1: Node.js 18+
# ---------------------------------------------------------------------------
step 1 "Checking Node.js..."
node_ok() {
  command -v node >/dev/null 2>&1 || return 1
  [ "$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)" -ge 18 ]
}
if node_ok; then
  say "   Node $(node --version) found."
else
  say "   Node.js is missing. Installing it into $TOOLS/node (no password needed)..."
  tarball=$(curl -fsSL --retry 3 "$NODE_INDEX/" \
    | grep -o "node-v[0-9.]*-${NODE_ARCH}\.tar\.gz" | head -1)
  [ -n "$tarball" ] || die "Could not reach nodejs.org. Check your internet connection and run this again."
  curl -fSL --retry 3 -o "$TOOLS/node.tar.gz" "$NODE_INDEX/$tarball" \
    || die "Downloading Node.js failed. Check your internet connection and run this again."
  rm -rf "$TOOLS/node" && mkdir -p "$TOOLS/node"
  tar -xzf "$TOOLS/node.tar.gz" -C "$TOOLS/node" --strip-components=1 \
    || die "Could not unpack Node.js."
  rm -f "$TOOLS/node.tar.gz"
  node_ok || die "Node.js was installed but will not run. Please report this."
  say "   Node $(node --version) installed."
fi

# ---------------------------------------------------------------------------
# Step 2: Python 3.10+
# ---------------------------------------------------------------------------
step 2 "Checking Python 3..."
# `command -v python3` finds Apple's stub even on a Mac with no Python: the
# stub exists only to pop a "install developer tools" dialog when run. So run
# it for real, and check the version while we are there.
py_ok() { [ -n "${PY:-}" ] && "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; }

PY=""
for candidate in "$TOOLS/python/bin/python3" "$(command -v python3 || true)"; do
  [ -n "$candidate" ] || continue
  PY="$candidate"
  py_ok && break
  PY=""
done

if [ -n "$PY" ]; then
  say "   $("$PY" --version) found."
else
  say "   Python 3.10+ is missing. Installing it into $TOOLS/python (no password needed)..."
  url=$(curl -fsSL --retry 2 "$PY_API" 2>/dev/null \
    | grep -o "https://[^\"]*cpython-3\.12[^\"]*${PY_ARCH}-install_only\.tar\.gz" | head -1)
  if [ -z "$url" ]; then
    # The API is rate-limited per IP; a pinned build keeps setup working anyway.
    url="https://github.com/astral-sh/python-build-standalone/releases/download/${PY_FALLBACK_TAG}/cpython-${PY_FALLBACK_VER}%2B${PY_FALLBACK_TAG}-${PY_ARCH}-install_only.tar.gz"
  fi
  curl -fSL --retry 3 -o "$TOOLS/python.tar.gz" "$url" \
    || die "Downloading Python failed. Check your internet connection and run this again."
  rm -rf "$TOOLS/python" && mkdir -p "$TOOLS/python"
  tar -xzf "$TOOLS/python.tar.gz" -C "$TOOLS/python" --strip-components=1 \
    || die "Could not unpack Python."
  rm -f "$TOOLS/python.tar.gz"
  PY="$TOOLS/python/bin/python3"
  py_ok || die "Python was installed but will not run. Please report this."
  say "   $("$PY" --version) installed."
fi

# ---------------------------------------------------------------------------
# Step 3: front-end dependencies
# ---------------------------------------------------------------------------
step 3 "Installing app dependencies..."
if [ -d node_modules ]; then
  say "   Already installed."
else
  npm install || die "npm install failed. Check your internet connection and run this again."
fi

# ---------------------------------------------------------------------------
# Step 4: Python backend
# ---------------------------------------------------------------------------
step 4 "Setting up the local backend..."
[ -d backend/.venv ] || "$PY" -m venv backend/.venv || die "Could not create the Python environment."
backend/.venv/bin/python -m pip install --upgrade pip -q
backend/.venv/bin/python -m pip install -q -r backend/requirements.txt \
  || die "Backend setup failed. Check your internet connection and run this again."
# Settings live in .env, which is per-machine and so is not in the repo.
[ -f .env ] || cp .env.example .env
say "   Backend ready."

# ---------------------------------------------------------------------------
# Step 5: the optional local AI
# ---------------------------------------------------------------------------
step 5 "Optional local AI..."
backend/.venv/bin/python -m backend.setup_ai || true

# ---------------------------------------------------------------------------
# Step 6: a launcher, then start
# ---------------------------------------------------------------------------
step 6 "Starting career-copilot..."
# Written here rather than shipped in the repo, for two reasons: a file created
# locally carries no quarantine flag, so it opens on a double-click without a
# Gatekeeper warning; and it can bake in the PATH that finds our own Node.
cat > career-copilot.command <<LAUNCHER
#!/bin/bash
# Double-click to start career-copilot. Close this window to stop it.
cd "\$(dirname "\$0")" || exit 1
export PATH="$TOOLS/node/bin:\$PATH"
npm run dev
LAUNCHER
chmod +x career-copilot.command

say ""
say "   Setup complete. The app window opens in a moment."
say "   Next time, double-click career-copilot.command in this folder."
say ""
npm run dev
