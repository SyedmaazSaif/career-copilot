# More job sources (scan coverage)

## Goal
Find more relevant jobs without AI, and understand why some boards stopped
contributing.

## Findings (verified live)
- **Hiring.cafe** now redirects `hiring.cafe` → `hiringcafe.com`, and the new
  domain is behind Cloudflare bot protection: every request returns **403**. It
  blocks automated access on purpose. The scraper now uses the new address and
  keeps skipping it gracefully while blocked.
- **LinkedIn** rate-limits; **Remote.co** times out intermittently.
- A **Bing RSS "search the web"** pass was tested and rejected: for job queries
  it returns dictionary/Wikipedia results, not job postings — it would pollute
  the job list.
- **Jobicy**'s free API (no key) returns 100 structured remote jobs per call and
  was verified live.

## What changed
- Added **Jobicy** as a new source (`fetch_jobicy`, one broad pass per scan; the
  profile matcher scores each job).
- Pointed **Hiring.cafe** at its new domain.
- Matching/scoring remains rule-based (**no AI**).

## Test plan
- `tests/test_jobicy.py` parses a saved real Jobicy reply (fixture).
- Full suite: 35 tests pass.
- End-to-end scan with Jobicy enabled needs a real app run.
