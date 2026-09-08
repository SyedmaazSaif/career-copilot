#!/bin/bash
# The file a Mac user double-clicks. It is deliberately tiny: all it does is
# fetch the real installer and run it, so this file almost never changes and
# the copy inside the downloadable zip does not go stale.
#
# Double-clicking a .command opens Terminal and shows the output, which is what
# we want -- the install takes a few minutes and silence would look like a
# hang. This is why it is a .command and not a .app.

REPO="${CAREER_COPILOT_REPO:-SyedmaazSaif/career-copilot}"
BRANCH="${CAREER_COPILOT_BRANCH:-main}"
URL="https://raw.githubusercontent.com/${REPO}/${BRANCH}/install-macos.sh"

# This file arrived inside a downloaded zip, so macOS flagged it and everything
# next to it. Clear that here: without it, the launcher created at the end of
# setup would hit the same "unidentified developer" wall on every start.
xattr -dr com.apple.quarantine "$(dirname "$0")" >/dev/null 2>&1

printf '\n'
printf '=====================================================\n'
printf '   Career Copilot - installer for macOS\n'
printf '=====================================================\n'
printf '\n'
printf 'Fetching the installer...\n\n'

script="$(mktemp -t career-copilot-install)" || {
  printf 'Could not create a temporary file. Please try again.\n\n'
  read -r -p "Press Return to close." _
  exit 1
}
trap 'rm -f "$script"' EXIT

if ! curl -fsSL --retry 3 -o "$script" "$URL"; then
  printf 'Could not download the installer.\n'
  printf 'Check your internet connection and try again.\n\n'
  read -r -p "Press Return to close." _
  exit 1
fi

# Run it as a file rather than piping it in, so the installer keeps this
# Terminal window as its input and can ask about the optional local AI.
bash "$script"
status=$?

if [ "$status" -ne 0 ]; then
  printf '\nThe installer stopped with an error (code %s).\n' "$status"
  printf 'The messages above say why.\n\n'
  read -r -p "Press Return to close." _
fi
exit "$status"
