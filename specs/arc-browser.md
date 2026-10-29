# Arc-style in-app browser

## Goal
Make the "Apply" window feel like Arc: a vertical sidebar of tabs, pinned
job boards, and a calm, minimal toolbar — plus secure local logins.

## Architecture (why it's built this way)
The browser is **not** built on Electron's deprecated `<webview>` tag, which is
fragile and was causing pages to fail to render. Instead, the main process
(`electron/main.js`) owns one `WebContentsView` per tab — the same pattern a
real multi-tab browser uses. The apply window's own page (`apply-window.html`)
is only the chrome (sidebar + toolbar). The main process is the source of truth
for tabs and pushes a state object (`apply:state`) to the chrome, which renders
it and sends back user intents (`apply:activate`, `apply:navigate`,
`apply:back`, …). Pages, profile autofill, and login fill all run inside each
tab's webContents, managed from the main process.

## Scope (first version)
1. **Sidebar with tabs** — keep several job pages open at once and click
   between them. The apply window becomes a single reused window; each job the
   user opens becomes a new tab instead of a new window.
2. **Pinned job boards** — LinkedIn, Indeed, etc. shown as small icon shortcuts
   in the sidebar and on the new-tab page.
3. **Clean toolbar** — back / forward / reload, an editable address bar, and a
   calmer, Arc-like look.
4. **Secure local logins** — save a site's username + password and fill them
   with one click. Encrypted with the OS keychain (Electron `safeStorage`),
   filled only on the exact site, and never auto-submitted.
5. **Keep what works** — profile Autofill and Attach CV (resume) stay, now
   applied to the active tab.

## Login security
- Passwords are encrypted with Electron `safeStorage` (macOS Keychain /
  Windows DPAPI); only an encrypted blob is written to disk.
- Stored per origin (scheme + host + port), never the full page URL.
- Fill only on an exact origin match, and only on the user's click; the app
  never submits a form for the user.
- Login code carries `// HUMAN REVIEW NEEDED` markers and is listed in
  `HONESTY.md`.

## Out of scope (ideas for later)
- Command bar (⌘T)
- Spaces (grouped tabs with colours)
- Little Arc quick-link window
- Browsing history
- Configurable pinned boards

## Test plan
- `node --check` on every changed `electron/*.js` file
- `npm run build` (frontend is unchanged; confirms nothing broke)
- `python -m unittest discover -s tests` (backend unchanged)
- GUI click-through needs a real app launch (flagged in `HONESTY.md`)
