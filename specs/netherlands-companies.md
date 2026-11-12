# Netherlands companies (visa-sponsor list)

## Goal
Add 18 Netherlands companies to the target-companies scanner so their open jobs
appear in the job list after every scan, with no manual step. All roles are
pulled (the matcher scores them); nothing is filtered to Pakistan or one
industry.

## How companies are scanned
- Companies live in the `company` table (name, ats, slug, enabled).
- Each scan (`backend/scan_manager.py` → `fetch_registry_jobs`) fetches every
  **enabled** company board via `backend/ats.py::fetch_board(kind, slug)`,
  then `ingest_jobs` scores and stores the results (deduped against existing
  jobs). Jobs are read back from the `job` table by `/api/jobs`.
- Added a seed script: `backend/seed_netherlands_companies.py` (idempotent).

## New connectors added in this work (backend/ats.py)
- `recruitee` — moved from "unverified" to verified: `{slug}.recruitee.com/api/offers`.
- `teamtailor` — `{slug}.teamtailor.com/jobs.json` (JSON Feed).
- `rss` — any RSS/Atom jobs feed (slug = the full feed URL; channel title = company).
- `optiver` — parses `https://www.optiver.com/sitemap.xml` (custom site).

## The 18 companies and their source

| # | Company | ATS kind | Slug / feed URL |
|---|---------|----------|-----------------|
| 1 | Optiver | optiver | (sitemap) https://www.optiver.com/sitemap.xml |
| 2 | Flow Traders | greenhouse | flowtraders |
| 3 | Maven Securities | ashby | maven |
| 4 | BlockTech | ashby | blocktech |
| 5 | Leaseweb | teamtailor | leaseweb |
| 6 | Bitvavo | ashby | bitvavo |
| 7 | Stream | ashby | stream |
| 8 | Plumerai | ashby | plumerai |
| 9 | GreenFlux | recruitee | greenflux |
| 10 | Gerimedica | recruitee | gerimedica |
| 11 | OLYX | recruitee | olyx |
| 12 | Secfi | — needs source — | secfi.com/careers (Homerun JS embed, slug not discoverable) |
| 13 | Flexport | greenhouse | flexport |
| 14 | A2G Consulting | rss | https://a2gtechnologies.com/jobs/feed/ |
| 15 | Wypoon Technologies | lever | wypoon |
| 16 | Riverflex | recruitee | riverflex |
| 17 | Rightangled | workable | rightangled |
| 18 | AMOLF | — needs source — | amolf.nl/vacancy-overview/ (custom WP, no public vacancy feed/API) |

Secfi and AMOLF are added as **disabled** rows named "… (needs source)" so they
are visible in Settings but never scanned.

## Test result (ran live)
- Fetched **580 jobs** across the 16 enabled companies (per-company counts in
  the table above; Optiver 222, Flexport 194, Flow Traders 44, Leaseweb 22,
  Rightangled 21, BlockTech 16, Bitvavo 15, A2G 10, Riverflex 9, OLYX 6,
  Stream 6, GreenFlux 5, Plumerai 4, Maven 3, Wypoon 2, Gerimedica 1).
- Ingest wrote **403 new jobs** to the database (177 were duplicates of jobs
  already present from other boards).
- Confirmed Product Manager / Business Analyst / Program Manager roles reached
  the list (e.g. Leaseweb "Business Analyst", Bitvavo "Lead Product Manager",
  Flexport "Senior Product Manager", "Technical Program Manager",
  "Associate Program Manager").

## Filters — checked, no change needed
- No category/keyword/industry/company exclusions are set, so nothing is
  dropped.
- `locations: ["Pakistan"]` only affects the location-aware boards (LinkedIn,
  Mustakbil); the company registry fetches each whole board globally, so the
  Netherlands jobs come through regardless.

## Known limits / still open
- Optiver titles are derived from the URL slug (no description fetched), so they
  are approximate; fetching each posting page would give richer text.
- Secfi (Homerun embed) and AMOLF (custom WordPress) still need a source; see
  the disabled rows.
- Ingest of these ~580 jobs is slow (~7–8 min) because scoring is CPU-bound —
  this is existing behaviour, not specific to this change.
