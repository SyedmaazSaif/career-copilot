# Direct link resolver

## Goal
For every job, find the job's **original posting on the hiring company's own
site or its applicant-tracking system (ATS)**, save it, and make the Apply
action use it. When it can't be found, fall back gracefully to the original
aggregator link. This only ever looks at **publicly available** postings — it
never logs in, bypasses, or scrapes behind any paywall.

## Background (what already existed)
- The app already had a `company_url` column on jobs, a manual "Find company
  site" button, redirect-following, ATS detection (Greenhouse/Lever/Ashby/
  Workable verified; Recruitee defensive; SmartRecruiters rejected for
  robots.txt), a company→ATS registry cache, and a hard-coded aggregator
  blocklist.
- Gaps this spec closes: structured resolution fields, an ordered resolver with
  slug-guessing across ATSes, verification before saving, a config-file
  blocklist, an automatic run during the scan, a backfill command, and UI that
  makes Apply use the direct link with clear labels.

## Data changes
Add to each job (existing `url` stays as the untouched original):
- `direct_url` — the resolved company/ATS link, or empty.
- `link_type` — `direct_job` | `careers_page` | `original`.
- `resolved_via` — `source_field` | `redirect` | `ats` | `search` |
  `careers_page` | `none` (plus `legacy` for migrated rows and `manual` for
  hand-pasted links).
- `resolved_at` — timestamp of the last resolve attempt.

The legacy `company_url` column is kept (never dropped) and any pre-existing
values are migrated into `direct_url` on upgrade.

## Resolver order (stop at first success)
A) **Source fields** — if the job's existing `url` already points at a
   non-aggregator domain, use it directly.
B) **Follow redirects** — request the aggregator link, follow redirects (no
   login); if the final address is a non-aggregator domain, use it. ~10s
   timeout, honest app user-agent.
C) **ATS lookup** — build candidate slugs from the company name (lowercase, no
   legal suffixes, hyphens), try the public job-board endpoints of Greenhouse,
   Lever, Ashby and Workable, and fuzzy-match title (and location when present)
   to find the exact posting. Cache the (company → ATS + slug) hit in the
   company registry so later jobs from the same company resolve instantly.
D) **Web search** — `"{company}" "{title}" careers` via the free DuckDuckGo /
   Bing endpoints; drop blocked aggregator domains; prefer ATS or company
   domains.
E) **Careers page fallback** — `"{company} careers"` → the company's own
   careers/jobs page. Saved with `link_type = careers_page`.
F) **Nothing found** — `direct_url` empty, `link_type = original`.

## Verify before saving
A `direct_job` result must: return HTTP success (not 404 / not a "job closed"
page), contain the job title (or a close match), and not be on the blocklist.
If verification fails, try the next method.

## Aggregator blocklist
One config file (`backend/aggregator_blocklist.json`) listing the domains to
reject as direct links: every source this app uses plus the common aggregators.
Easy to edit — one domain per line, no code change needed.

## When it runs
- Automatically at the end of every scan, for jobs that already passed ingest
  (i.e. they are stored, so they passed category/keyword/company filters).
- Each job is resolved once; `original` jobs retry at most once per day.
- Capped per scan (default 10 jobs, highest score first) with small delays and
  per-host rate limiting, so no site blocks us and a scan stays quick.
- A resolver failure never crashes the scan — it is logged and skipped.
- A backfill command (`python -m backend.resolve_backfill`) runs the resolver
  over already-saved jobs, with a summary table.

## What the user sees
- The main Apply button opens `direct_url` when present, else the original.
- A small label: "Company site" (`direct_job`), "Careers page — find the job
  there" (`careers_page`), or "Original link — may be paywalled" (`original`).
- The original aggregator link is always kept as a secondary link.

## Test plan
- Unit tests for slug building, title matching, blocklist, and resolution
  (mocked network).
- Run the resolver on ≥20 real saved jobs via the backfill command and report
  how many resolved as `direct_job` / `careers_page` / `original` and by which
  method.
- Open-check 5 `direct_job` links (programmatic GET + title match + domain
  check) to confirm they load the right job with no paywall.

## Out of scope (later)
- ATS connectors beyond the verified set (SmartRecruiters is robots-blocked,
  Recruitee unverified).
- Editing the blocklist from inside the UI.
