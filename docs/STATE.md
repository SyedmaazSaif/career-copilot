# STATE

Living state for the next run. Overwrite, never append. No run history — the
commit log is that record.

## Open findings (ranked)

1. **Sources are office/tech-skewed; keyless ATS boards don't reach non-office
   employers.** Verified: greenhouse/`mayoclinic`, `caterpillar`, `starbucks`,
   `target`, `walmart`, `ford`, etc. are all 404 — hospitals and manufacturers
   use Workday/Taleo, which have no keyless API. The one general source that
   works, LinkedIn, does return welder and nurse jobs when asked (20 each,
   verified live). Adding The Muse (414K jobs, keyless, `themuse.com/api/public/jobs?page=1`)
   would widen the general pool; Jobicy is ~90% sales/dev — not worth it.
2. **Cold start scans nothing now** (queries derive from the profile, which is
   empty until a résumé is uploaded). Correct, but the Jobs screen needs an
   honest empty state: "upload your résumé to search for your roles."
3. **Single-word skills that are also common verbs false-positive** (a welder's
   "Grinding" matched a Discord engineering-manager post). Residual ~8/100.
4. **Title tokenizer drops 2-char abbreviations** ("RN", "IT", "AI", "ML"), so
   "RN Case Manager" shares no title word with "Registered Nurse".

## Decisions made

- **SCORE_VERSION 4**: arrangement and eligibility lift a job in proportion to
  how well it already matches; role fit awards no free points. Irrelevant
  remote/open jobs dropped from ~30 to ~0-8; the accountant's real jobs stayed
  on top.
- **Resume parsing is deterministic now** (`backend/resume.py`): the no-AI
  heuristic extracts title, skills (incl. "Category: items" competencies),
  work history ("Role | Company" blocks with bullets) and education. The local
  model still enriches and wins when available. This fixed an observed crash
  where the 8B model dropped the experience-extraction call and left the
  profile with zero skills/experience.
- **Scan queries derive from the résumé** (`backend/matching.derive_queries`):
  the scanner used a hardcoded list of 20 product-manager titles, so the DB
  only ever filled with PM/office jobs and a welder/nurse saw nothing. Queries
  now come from the user's titles + distinctive skills, capped at 15. Verified
  live: `run_scan(queries=["welder"])` over LinkedIn returns 20 welding jobs.

## Ideas rejected

- **Hybrid retrieval (FTS5 BM25 + embeddings RRF)** — no embeddings exist in the
  code; the dominant matching failure was the constraint floor, not the text
  axis. Revisit only if embeddings land.
- **Suppressing "Grinding" / other ambiguous skill words** — would hurt real
  machinist/welder matches (constraint 1).
- **ATS company-direct breadth (Greenhouse/Lever/Ashby/Workable) to reach
  non-office employers** — verified those boards don't host hospitals or
  manufacturers; the employers use Workday/Taleo. Not a path to welder/nurse
  jobs.
- **Adding Jobicy** — remote-only and ~90% sales/dev; dilutes rather than helps.

## Job sources

Endpoints verified live this run (2026-10-22, all keyless, no account):

- LinkedIn — `fetch_linkedin(query, location)` returns 20 real results per call;
  returns welder and nurse jobs. Fragile (rate-limits ~page 10); treat a miss
  as an outage, never as "jobs closed".
- Lever — `https://api.lever.co/v0/postings/{slug}?mode=json` → 200 (`leverdemo`).
- Greenhouse — `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs` → 200
  (`greenhouse`); non-tech slugs 404.
- Himalayas — `https://himalayas.app/jobs/api` → 200.
- Arbeitnow — `arbeitnow.com/api/job-board-api`; office/tech only (0 "welder").
- The Muse — `https://www.themuse.com/api/public/jobs?page=1` → 200, 414K total,
  page_count 20701; office-heavy but cross-industry by volume.

DB sources today: linkedin (4095), weworkremotely (647), himalayas (482),
arbeitnow (222), remotive (56), mustakbil (41), remoteok (9).

## Design constraints

- Relevance comes only from the uploaded résumé (constraint 1). Nothing in
  `backend/matching.py` may name an industry, company or job title — and the
  scan queries must come from the profile too, never a fixed list.
- `backend/cv_boundary.py` never invents résumé claims (constraint 2).
- Free, local, no account, no key (constraint 3). New deps must not break this.
- `docs/MATCHING.md` is the matching contract — update it in the same commit as
  any change to `matching.py`/`taxonomy.py`.
- Scoring is pure stdlib (no sklearn/numpy) — keep it that way.
- Tests: `backend/.venv/bin/python -m unittest tests.test_matching tests.test_resume tests.test_queries`
  (stdlib unittest; no pytest). Build: `npx vite build`.
- Backend runs under `backend/.venv` (Python 3.12); system python3 is 3.9.
- Desktop launcher: `Career Copilot.app` (gitignored) runs
  `node scripts/start.js` headless; a Finder alias on the Desktop starts it.
