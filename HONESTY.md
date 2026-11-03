# HONESTY.md

## Tested and working (ran locally, saw the result)
- **CV headline fix** — a generated CV no longer prints the job's title under
  the name. Generated a real PDF against the live profile for a fake
  "Senior Technical Product Manager - AvaCloud" job and read the first lines:
  the name is followed by the profile's own title ("Product Manager — Consumer
  Platforms, Fintech & AI Products"), while the job title is kept only in the
  filename. The "Target title" field that caused the mix-up was removed from
  the job page.
- **Country filter** — new "Any country" dropdown on the jobs screen derives a
  country from each job's free-text location (`src/countries.js`). The mapping
  was exercised with node against real location strings ("USA" → United States,
  "Corby, England, United Kingdom" → United Kingdom, "New South Wales, Australia"
  → Australia, "Remote - US only" → United States). `npm run build` succeeds; the
  Settings section is relabelled "Countries to search". The dropdown itself needs
  a real app launch to click through (see Partial).
- **Country tagging (backend)** — new `country` column on jobs, derived from
  location at ingest and backfilled on the live DB (5,494 of 10,674 jobs got a
  country). `derive_country` unit-tested (6 tests, including "New South Wales"
  → Australia and "Northern America, LATAM…" → no country). Verified `JobOut`
  returns the country ("USA" → United States). Career-page jobs flow through the
  same ingest path, so they are tagged too. Full suite now 70 tests pass;
  `npm run build` succeeds; `backend.main` imports cleanly.
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
- Existing suite: `python -m unittest discover -s tests` → 64 tests pass.
- **AI provider choice** — new DeepSeek / OpenAI-compatible client + `llm` dispatch
  unit-tested (success, provider error, JSON parsing, fence stripping, provider
  routing); 10 tests pass. `backend.main` imports cleanly with the new
  `/api/ai/config` endpoints.
- **Claymorphism reskin** — the whole UI (main app + apply window) moved from the
  dark neon theme to a light pastel clay theme: lavender ground, white clay
  surfaces, soft violet accent, Fredoka + Nunito typography, inner+outer clay
  shadows. `npm run build` succeeds; electron files pass `node --check`; all text
  accent colours verified ≥ 4.5:1 contrast on their backgrounds.
- **Own CV upload** — new `/api/own-cv` router unit-tested (upload stores the
  file + row, empty file and wrong extension rejected, newest-first list, delete
  removes the file). 5 tests pass; `backend.main` imports with the new route.
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
- **AI provider (end-to-end)** — the DeepSeek client is unit-tested with mocked
  HTTP, but a real DeepSeek/Custom API call, and the Settings key-save flow
  (safeStorage → backend restart → config re-read), need a real app launch with
  a real key to confirm. No live paid call has been made.
- The desktop app was not launched in this environment — no GUI click-through.
  All UI, apply-window buttons, and the `cv_folder` migration against the live
  database (runs on next app start) need a real launch to confirm.
- **Claymorphism reskin** — verified by build + syntax + contrast checks only; the
  actual look (soft 3D clay surfaces, fonts, hover/press feel) needs a real app
  launch to confirm it reads as intended.
- Lever and Ashby live fetches were not run (only Greenhouse verified live).
- **Arc-style browser UI** — the tab sidebar, pinned boards, and save/fill login
  were not launched in a GUI; they pass syntax/build checks only. Tab switching,
  cookie sharing across tabs, and login save/fill need a real app launch.
- **Password import + company search UI** — the "Import from file" button and the
  "Find a company by name" field build cleanly but need a real app launch to
  confirm end-to-end (file picker → import; name → resolve → add).
- **Own CV upload UI + apply-window attach** — the "Your own resume" box on the
  Profile page and the updated `Attach CV` button (now prefers the user's own CV)
  build cleanly and pass syntax checks, but need a real app launch to confirm the
  upload → attach flow end-to-end.
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
- **AI API key** — the DeepSeek / custom-model key is stored with Electron
  `safeStorage` (OS keychain/DPAPI), passed to the backend only as an in-memory
  environment variable, and never written to a file or logged. The Settings UI
  never shows the saved key back. // HUMAN REVIEW NEEDED: API key handling
- **Gmail alerts (skipped)** — not built. If revisited later, it must be
  READ-ONLY (never send, delete, label or change read state). // HUMAN REVIEW
  NEEDED: email access
