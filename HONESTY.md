# HONESTY.md

## Tested and working (ran locally, saw the result)
- **CV output** — generated on a throwaway DB with a fake profile: filename
  `Syed_Maaz_Saif_Product_Manager.pdf`, PDF + Word copy both written to the
  chosen `cv_folder`, PDF text extractable (ATS-safe).
- **Cover letters + screener answers** — fact-based, cover letter saved as PDF.
- **Follow-up assistant** — returns only "Applied" jobs with no reply after 5
  days (correctly excluded a replied job).
- **"Where am I stuck"** — diagnosis returns the expected heading.
- **ATS keyword check** — correct missing keywords + profile tips.
- **Company careers-page scanning** — ATS detection unit-tested (Greenhouse,
  Lever, Ashby, embed URL, no-ATS); live Greenhouse "stripe" fetch returned 714
  jobs.
- Existing suite: `python -m unittest discover -s tests` → 30 tests pass.
- `backend.main` imports cleanly; `npm run build` succeeds; electron files pass
  `node --check`.
- **Arc-style browser (files)** — `electron/main.js`, `electron/apply-preload.js`
  and the inline script in `electron/apply-window.html` pass `node --check`, and
  the frontend still builds cleanly. The window itself needs a real launch.
- **Browser architecture** — rebuilt on `WebContentsView` (one managed view per
  tab, owned by the main process) instead of the deprecated `<webview>` tag,
  which was causing pages to fail to render.

## Partial / unproven
- The desktop app was not launched in this environment — no GUI click-through.
  All UI, apply-window buttons, and the `cv_folder` migration against the live
  database (runs on next app start) need a real launch to confirm.
- Lever and Ashby live fetches were not run (only Greenhouse verified live).
- **Arc-style browser UI** — the tab sidebar, pinned boards, and save/fill login
  were not launched in a GUI; they pass syntax/build checks only. Tab switching,
  cookie sharing across tabs, and login save/fill need a real app launch.

## Needs human review
- Privacy: generated files and the profile stay local. `cv_folder` is a user-set
  path; no name/path is hard-coded. // HUMAN REVIEW NEEDED: resume/profile data
- "Attach CV" reveals the file in Finder/Explorer (one drag away); it does not
  inject files into a job site's upload field — browsers block that, and the
  app's rule is "you apply yourself; the app never submits for you".
- **Local logins** — the in-app browser can save website passwords (encrypted
  via the OS keychain) and fill them on the saved site. // HUMAN REVIEW NEEDED:
  password handling
