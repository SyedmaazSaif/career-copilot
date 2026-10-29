# Import logins from another browser

## Goal
Let the user bring their saved website passwords into the in-app browser's
local login store, so they don't have to re-enter them.

## How it works
1. In the other browser (Chrome, Safari, Firefox, …) the user uses the built-in
   "Export passwords" action and saves a CSV file.
2. In the apply window's **Logins** panel they tap **Import from file** and pick
   that CSV.
3. The app parses the CSV (tolerant of Chrome and Firefox column layouts),
   keeps only rows with a usable URL and password, and stores each one with the
   existing encrypted `safeStorage` path — keyed by origin, never logged.

## Security
- Passwords are encrypted with Electron `safeStorage` (macOS Keychain / Windows
  DPAPI) before writing to disk; plaintext is never logged or echoed.
- Import is `// HUMAN REVIEW NEEDED` and listed in `HONESTY.md`.

## Honest limits
- **Passwords** import fine. **Passkeys** generally cannot be copied between
  browsers (deliberate security design), so those stay in the user's original
  browser. This is documented for the user.

## Out of scope
- Directly reading another browser's on-disk encrypted store (modern Chrome
  uses app-bound encryption that other apps cannot decrypt).

## Test plan
- `node --check` on changed electron files
- CSV parser exercised against a small fixture (Chrome + Firefox shapes)
- `npm run build` + backend unit tests
