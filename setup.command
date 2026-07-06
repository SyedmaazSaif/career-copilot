#!/bin/bash
# career-copilot setup for macOS. Double-click this file in Finder, or run it
# in Terminal. It installs what the app needs and starts it.
cd "$(dirname "$0")" || exit 1

echo "====================================================="
echo "   career-copilot  -  one-time setup (macOS)"
echo "====================================================="
echo "Leave this window open while using the app."
echo

# ---------- Step 1: Node ----------
echo "[1/4] Checking Node.js..."
if ! command -v node >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "   Node not found. Installing with Homebrew..."
    brew install node
  else
    echo "   Node.js is not installed. Install it from https://nodejs.org (LTS),"
    echo "   then run this again."
    read -r -p "Press Return to close." _
    exit 1
  fi
fi
echo "   Node $(node --version) found."

# ---------- Step 2: Python ----------
echo "[2/4] Checking Python 3..."
if ! command -v python3 >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "   Python not found. Installing with Homebrew..."
    brew install python
  else
    echo "   Python 3 is not installed. Install it from https://python.org/downloads,"
    echo "   then run this again."
    read -r -p "Press Return to close." _
    exit 1
  fi
fi
echo "   $(python3 --version) found."

# ---------- Step 3: dependencies ----------
echo "[3/4] Installing dependencies..."
if [ ! -d node_modules ]; then
  npm install || { echo "   npm install failed."; read -r -p "Press Return." _; exit 1; }
fi
if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
fi
backend/.venv/bin/python -m pip install --upgrade pip -q
backend/.venv/bin/python -m pip install -q -r backend/requirements.txt || {
  echo "   Backend setup failed."; read -r -p "Press Return." _; exit 1; }
echo "   Ready."

# ---------- Step 4: launch ----------
echo "[4/4] Starting career-copilot..."
echo
echo "Setup complete. The app window opens in a moment."
echo "Next time, run this file again (or 'npm run dev' in Terminal) to start it."
echo
npm run dev
