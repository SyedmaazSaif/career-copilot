# STATE

Living state for the next run. Overwrite, never append. No run history — the
commit log is that record.

## Open findings (ranked)

1. **Coverage is the binding constraint on "every profession".** The local DB
   (~5,552 jobs) is a remote/office corpus: 0 job titles contain "welder",
   "nurse", "electrician", "plumber", "mechanic", "carpenter"; ~90% are
   LinkedIn/WeWorkRemotely/Himalayas remote office roles. A welder or nurse
   gets *nothing* relevant to rank no matter how good matching is. After the
   SCORE_VERSION 4 fix they honestly see near-0 scores — correct, but useless.
   Next run: add genuinely cross-industry / ATS-native sources (The Muse,
   Greenhouse, Lever, Ashby, Workable) so blue-collar and clinical roles exist
   to match. Measured live this run: 0/5552 titles for welder/nurse/electrician.

2. **Single-word skills that are also common verbs false-positive.** A welder's
   "Grinding" matched Discord's "Engineering Manager, Notifications" (the word
   appears in office prose). Residual ~8/100 after the floor fix. A clean,
   profession-agnostic fix is not obvious — suppressing "grinding" would hurt
   real machining/welder matches. Leave until coverage brings real trade roles.

3. **Title tokenizer drops 2-char abbreviations** ("RN", "IT", "AI", "ML"), so
   "RN Case Manager" shares no title word with "Registered Nurse". Consider
   abbreviation-aware title matching once coverage exists.

4. **All-zero list has no empty state.** When nothing matches, the UI shows a
   wall of 0% rows. A "no strong matches for your profile — expand sources or
   widen settings" empty state would stop a welder from thinking the app is
   broken. Cheap, good follow-up after #1.

## Decisions made

- **Shipped SCORE_VERSION 4 (2026-10-22): arrangement and eligibility now lift
  a job in proportion to how well it already matches; role fit awards no free
  points.** Evidence: before the change a welder's #1 job was "Engineering
  Manager, Notifications" @ Discord at 31/100 (decomposed: skills 6 from a
  false-positive "Grinding", role 5, arrangement 10, eligibility 10, text 0).
  The 20-point arrangement+eligibility floor plus a 5–10 role floor meant every
  remote/open job scored 25–31 regardless of fit. After: irrelevant jobs score
  0–8; the accountant's real jobs stay on top (junk pushed from ~38–41 down to
  ~19–23). The change is profession-agnostic — it removes noise for everyone.

## Ideas rejected

- **Hybrid retrieval (FTS5 BM25 + existing embeddings via RRF)** — the inherited
  leading candidate. Rejected this run: there *are no embeddings* anywhere in
  the code (the "optional semantic layer" in MATCHING.md was never implemented;
  matching.py is pure TF-IDF, no FTS tables, no embedding column). The dominant
  failure was the additive constraint floor (20–25 free points), not the
  20-point text-similarity method. Revisit only if/when embeddings exist.
- **Suppressing "Grinding" / other ambiguous skill words** — would violate the
  "helps welders, not just office workers" constraint. See finding #2.
- **Adding cross-industry sources this run** — real and needed, but
  network-dependent, needs saved fixtures to test, and ranked below the
  matching-floor fix on impact-per-unit-work (which helps every profession
  deterministically). This is finding #1 for the next run.

## Job sources

Endpoints verified live this run (2026-10-22, all keyless, no account):

- Lever — `https://api.lever.co/v0/postings/{slug}?mode=json` → 200 (tested
  `leverdemo`). Inherited note: `netflix` is dead (Netflix left Lever).
- Greenhouse — `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs` → 200.
- Himalayas — `https://himalayas.app/jobs/api` → 200.

Inherited knowledge (re-verify before relying): The Muse
`themuse.com/api/public/jobs?page=1` (cross-industry, `categories` may be
empty); Arbeitnow `arbeitnow.com/api/job-board-api` (~13/page, no meta/next —
paginate `?page=N`, stop on empty `data`); Jobicy
`jobicy.com/api/v2/remote-jobs?count=N`; Ashby
`api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` (without
that param there is NO compensation field); Workable
`apply.workable.com/api/v1/widget/accounts/{slug}?details=true` (`description`
is HTML — strip before matching); SmartRecruiters and Workday CxS unverified.

Gotcha: the DB's actual sources are `linkedin` (4095), `weworkremotely` (647),
`himalayas` (482), `arbeitnow` (222), `remotive` (56), `mustakbil` (41),
`remoteok` (9). LinkedIn and WeWorkRemotely are in the DB but NOT in the keyless
list above — verify how they're fetched before assuming coverage.

ATS slug liveness must report three states — dead slug, live employer with zero
openings, live employer with openings — never collapse them.

## Design constraints

- Relevance comes only from the uploaded résumé (constraint 1). Nothing in
  `backend/matching.py` may name an industry, company or job title.
- `backend/cv_boundary.py` never invents résumé claims (constraint 2).
- Free, local, no account, no key (constraint 3). New deps must not break this.
- `docs/MATCHING.md` is the matching contract — update it in the same commit as
  any change to `matching.py`/`taxonomy.py`.
- Scoring is pure stdlib (no sklearn/numpy) — keep it that way; it runs on a
  laptop during scans.
- Tests: `backend/.venv/bin/python -m unittest tests.test_matching -v` (stdlib
  unittest; no pytest installed). Build: `npx vite build`.
- Backend runs under `backend/.venv` (Python 3.12); system python3 is 3.9.
- The matching engine was inherited uncommitted (repo was moved); committed as
  baseline `fbb2062` before SCORE_VERSION 4 landed.
