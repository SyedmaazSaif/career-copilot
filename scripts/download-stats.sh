#!/bin/bash
# Print download counts for every release asset, read-only, no login.
# Uses only curl (unauthenticated GitHub API) and a small JSON parser.
#
#   bash scripts/download-stats.sh            # SyedmaazSaif/career-copilot
#   bash scripts/download-stats.sh <owner>/<repo>

set -u

REPO="${1:-SyedmaazSaif/career-copilot}"
API="https://api.github.com/repos/${REPO}/releases"

command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }

curl -fsSL "$API" \
  | python3 -c '
import sys, json
try:
    data = json.load(sys.stdin)
except Exception as e:
    print("Could not parse the GitHub API response:", e, file=sys.stderr)
    sys.exit(1)

if isinstance(data, dict):
    print("GitHub API message:", data.get("message", "unknown error"), file=sys.stderr)
    sys.exit(1)

total = {}
grand = 0
for r in data:
    tag = r.get("tag_name", "?")
    assets = r.get("assets", [])
    print(f"== {tag} ==")
    for a in assets:
        name = a.get("name", "?")
        count = a.get("download_count", 0)
        total[name] = total.get(name, 0) + count
        grand += count
        print(f"  {count:>7}  {name}")

print()
print("== Total across releases ==")
for name in sorted(total):
    print(f"  {total[name]:>7}  {name}")
print(f"  {grand:>7}  TOTAL")
'
