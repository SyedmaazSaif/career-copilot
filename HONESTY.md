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
- Existing suite: `python -m unittest discover -s tests` → 49 tests pass.
- **Jobicy source** — `fetch_jobicy` fetched 100 real jobs live, and a fixture
  test (`tests/test_jobicy.py`) parses a saved real Jobicy reply.
- **Scan-coverage diagnosis** — verified live that Hiring.cafe now redirects to
  `hiringcafe.com` behind Cloudflare (403 blocks), and that a Bing-RSS "search
  the web" pass returns dictionary/Wikipedia pages rather than jobs (so it was
  not shipped).
- `backend.main` imports cleanly; `npm run build` succeeds; electron files pass
  `node --check`.
- **Arc-style browser (files)** — `electron/main.js`, `electron/apply-preload.js`
  and the inline script in `electron/apply-window.html` pass `node --check`, and
  the frontend still builds cleanly. The window itself needs a real launch.
- **Browser architecture** — rebuilt on `WebContentsView` (one managed view per
  tab, owned by the main process) instead of the deprecated `<webview>` tag,
  which was causing pages to fail to render.
- **Password CSV import** — the CSV parser was exercised against Chrome and
  Firefox export shapes (quoted fields, embedded commas and doubled quotes) and
  produced the expected rows.
- **Company-by-name resolver** — `resolve_source` unit-tested (Greenhouse board,
  generic careers page, not-found, empty name rejected); 4 tests pass.
- **Job discovery upgrade** — live-verified connectors for Greenhouse, Lever,
  Ashby, Workable, Hacker News "Who is hiring" and The Muse. A real scan (2
  queries, 9 sources) returned 658 unique jobs, ~364 from the new sources
  (HN 224, Jobicy 100, Muse 40). Location-eligibility, title expansion, skills
  weighting, dedup and the auto-growing registry are unit-tested.

## Partial / unproven
- The desktop app was not launched in this environment — no GUI click-through.
  All UI, apply-window buttons, and the `cv_folder` migration against the live
  database (runs on next app start) need a real launch to confirm.
- Lever and Ashby live fetches were not run (only Greenhouse verified live).
- **Arc-style browser UI** — the tab sidebar, pinned boards, and save/fill login
  were not launched in a GUI; they pass syntax/build checks only. Tab switching,
  cookie sharing across tabs, and login save/fill need a real app launch.
- **Password import + company search UI** — the "Import from file" button and the
  "Find a company by name" field build cleanly but need a real app launch to
  confirm end-to-end (file picker → import; name → resolve → add).
- **Jobicy in a real scan** — verified `fetch_jobicy` alone; a full scan with
  Jobicy enabled (and its jobs ingested + scored) needs a real app run.
- **Recruitee connector** — implemented but not verified: no live public
  endpoint found (`{company}.recruitee.com/api/offers` 404s; the app API is
  auth-gated). Kept disabled-by-default, returns [].
- **Web-search ATS discovery** — implemented but returns ~0 boards in practice:
  DuckDuckGo challenges, Bing returns no `site:` results, Mojeek disallows
  `/search`. Auto-grow is the effective discovery path.
- **Gmail alerts ("alerts inbox" source)** — skipped by the user's request. No
  Google sign-in or account access is requested; the source is off and not built.
- **Settings UI (target companies, exclusion words/industries)** — builds cleanly
  but needs a real app launch to confirm end-to-end.

## Needs human review
- Privacy: generated files and the profile stay local. `cv_folder` is a user-set
  path; no name/path is hard-coded. // HUMAN REVIEW NEEDED: resume/profile data
- "Attach CV" reveals the file in Finder/Explorer (one drag away); it does not
  inject files into a job site's upload field — browsers block that, and the
  app's rule is "you apply yourself; the app never submits for you".
- **Local logins** — the in-app browser can save website passwords (encrypted
  via the OS keychain) and fill them on the saved site. // HUMAN REVIEW NEEDED:
  password handling
- **Password import** — imports passwords from a user-chosen CSV (exported from
  another browser); each is encrypted via the OS keychain before writing to disk
  and nothing is logged. // HUMAN REVIEW NEEDED: password import
- **Gmail alerts (skipped)** — not built. If revisited later, it must be
  READ-ONLY (never send, delete, label or change read state). // HUMAN REVIEW
  NEEDED: email access
