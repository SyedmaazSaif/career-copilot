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
URL="https://github.com/${REPO}/releases/latest/download/install-macos.sh"

# This file arrived inside a downloaded zip, so macOS flagged it and everything
# next to it. Clear that here: without it, the launcher created at the end of
# setup would hit the same "unidentified developer" wall on every start.
here="$(dirname "$0")"
xattr -dr com.apple.quarantine "$here" >/dev/null 2>&1
# A second, separate flag: macOS also stamps files with com.apple.macl (an
# access list tied to whichever app last touched them) whenever they are
# copied from another Mac, an external drive, or AirDrop. It is not Gatekeeper
# and "Open Anyway" does not clear it -- it silently denies access to a file's
# own owner, admin rights or not. Clearing it here costs nothing on a normal
# GitHub download and fixes it on a copied one.
xattr -dr com.apple.macl "$here" >/dev/null 2>&1

printf '\n'
printf '=====================================================\n'
printf '   Career Copilot - installer for macOS\n'
printf '=====================================================\n'
printf '\n'

# Some Macs (especially a freshly set up one) have not yet granted Terminal
# permission to work inside Desktop, Documents or Downloads. When that is the
# case every step below would fail with a confusing "Permission denied" or
# "You don't have permission" partway through. Catch it here instead, with an
# explanation a non-technical user can actually act on.
probe="$here/.cc-write-test-$$"
if ! { : > "$probe"; } 2>/dev/null; then
  printf 'macOS is blocking Terminal from working in this folder.\n\n'
  printf 'This is a privacy setting, not a real permissions problem -- it\n'
  printf 'happens on new Macs until Terminal is explicitly allowed in.\n\n'
  printf 'Fix it in one step:\n'
  printf '  1. Open System Settings -> Privacy & Security -> Files and Folders.\n'
  printf '  2. Find Terminal, and turn on access to Desktop Folder,\n'
  printf '     Documents Folder, and Downloads Folder.\n'
  printf '  3. Come back here and open this file again.\n\n'
  read -r -p "Press Return to close." _
  exit 1
fi
rm -f "$probe"

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
