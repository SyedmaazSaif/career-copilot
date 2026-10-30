# Job discovery upgrade

## Goal
Find as many relevant jobs as possible for any user, from free sources that
allow automated access, with rules-based matching (no AI, no paid keys).

## Hard rules applied
- Honest User-Agent (`career-copilot/0.8.3 …`) everywhere; no fake browser UA.
- Per-host rate limiting, 429/5xx backoff, response caching (`http_client.py`).
- robots.txt checked before adding a source or fetching a pasted URL.
- Never bypass bot protection; 403/challenge/robots-disallow → skip and log.

## Part 1 — ATS connectors + company registry
- `backend/ats.py`: Greenhouse/Lever/Ashby (reuse) + Workable (new, verified
  live) + Recruitee (kept defensive, unverified). SmartRecruiters rejected
  (robots.txt disallows all bots).
- `Company` table + `backend/company_registry.py`: dedupe by (ats, slug),
  auto-grow, drop after 3 empty/broken runs.
- Settings UI: "Target companies" add/remove.

## Part 2 — discovery
- Aggregators added: The Muse, Hacker News "Who is hiring" (both verified).
  JobsPresso rejected (empty feed).
- Auto-grow registry from ATS URLs in seen jobs.
- `web_discovery.py`: capped web-search pass (returns ~0 in practice — free
  search engines block `site:` queries).

## Part 3 — matching
- `title_expansions.json` (editable) + `expand_titles`.
- Skills weighted by where they appear; years-of-experience estimate.
- Location eligibility rewritten (region/timezone/country/visa rules).
- Exclusion keywords + excluded industries (config + ingest).
- Dedup prefers direct company (ATS) links over aggregator links.

## Part 4 — blocked sites + inbox + link drop
- Hiring.cafe → `hiringcafe.com`, skipped while Cloudflare 403 (logged).
- "Send to Copilot": existing "Add job by URL" now checks robots.txt first.
- Gmail alerts: deferred (needs Google OAuth setup — see HONESTY).

## Part 5 — reliability
- Per-source health summary (`ScrapeRun.source_health`).
- 49 tests: connector parsing (fixtures), dedup, eligibility, title expansion,
  registry auto-grow/drop.

## Verification (real, ran locally)
- Live-verified sources: Greenhouse, Lever, Ashby, Workable, HN, The Muse,
  Jobicy, Remotive, RemoteOK, WWR, Himalayas, Arbeitnow.
- Real scan (2 queries, 9 sources): 658 unique jobs; new sources contributed
  ~364 (HN 224, Jobicy 100, Muse 40).
