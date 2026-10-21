# How matching works, and why

This is the design note for job relevance in career-copilot: what the scoring
does, what evidence it rests on, and which failures it was written to prevent.
Read this before changing `backend/matching.py` or `backend/taxonomy.py`.

The governing constraint: **career-copilot is for anyone.** A nurse, a welder,
a tax accountant and a product manager all have to get good matches from the
same code. Nothing in the scoring may be tuned to one person's background —
everything comes from the résumé the user uploads.

---

## What was wrong before

The first version scored a job against five weighted components. Four of them
had defects serious enough to make the score close to noise.

| Problem | Effect |
|---|---|
| `classify_work_type` returned `remote` if the word "remote" appeared anywhere in the job text | Nearly every posting says it somewhere, so almost every job scored full marks on the 15-point arrangement axis |
| `DOMAIN_KEYWORDS` was a fixed list — voice AI, IVR, MNO, VAS, Pakistan, India | Telecom roles were pushed up every user's list, whoever they were |
| Skill matching fell back to the longest word in a skill name | "Product Management" collapsed to "product", which appears in most postings, so most jobs drew half credit for a skill they did not want |
| Titles were matched against a hardcoded product/partnerships list | Every other profession scored "ambiguous" — 45% of the title weight — regardless of fit |
| `score_job` ran only on insert | Editing your résumé or settings never changed a single score already in the list |

Dedupe had its own bug. The fuzzy threshold of 0.92 on title+company is
squarely inside the range where genuinely different roles collide: "Sales
Manager (Dubai)" and "Sales Manager (Abu Dhabi)" are about 92% similar
([dev.to](https://dev.to/get_anything/the-same-job-is-posted-on-three-boards-heres-how-to-deduplicate-job-listings-properly-2862)).
The same comparison guards the dismissed-job blocklist, so dismissing a role in
one city could silently suppress a real role in another.

---

## What the research says

### On matching

**Layered matching beats keywords.** The standard architecture is keyword
overlap, then semantic similarity over embeddings, then structured field
extraction. Semantic layers report 29–36% better accuracy than keyword-only
matching ([Resume Matcher](https://resumematcher.fyi/blog/how-resume-matching-algorithms-actually-work)).

**Explainable classical NLP gets most of the way there.** ResumeIQ scores
compatibility as `0.40 × TF-IDF cosine + 0.40 × skill match + 0.20 × keyword
match`, with no LLM, specifically so every number traces back to source text
([ResumeIQ](https://github.com/smitthakkar11/ResumeIQ)). That property matters
here: a score the user cannot interrogate is a score they will not trust.

**Content-based recommenders are the right family, with a known weakness.**
Aggarwal's textbook notes content-based methods excel "for new items, when
sufficient rating data are not available" — which describes every job posting
ever scraped — but warns they produce "obvious recommendations" lacking
diversity, and struggle with new users who have no history
([Aggarwal, *Recommender Systems: The Textbook*](https://link.springer.com/book/10.1007/978-3-319-29659-3)).
Both caveats apply directly: we need a cold-start path for someone who has not
uploaded a résumé yet, and a guard against the list collapsing into fifty
near-identical postings.

**Embedding thresholds have published defaults.** The ESCO skill extractor uses
`all-MiniLM-L6-v2` with cosine thresholds of 0.6 for skills and 0.55 for
occupations, MIT-licensed
([esco-skill-extractor](https://github.com/KonstantinosPetrakis/esco-skill-extractor)).
Useful calibration for the optional semantic layer rather than inventing
cut-offs.

### On explanations — this changed the design

**Narrative explanations beat scores.** A review of explainable person–job
recommendation finds template sentences of the form *"We recommend this
position because your [skill] matches the job's [requirement]"* were "more
trustworthy than raw scores alone," and that users need to see *which specific
attributes* drove the match, not a confidence number
([Frontiers in AI](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1660548/full)).

**Explanations should support a decision, not sell one.** The recommendation is
to pivot "from persuasive to supportive," grounding every explanation in the
source CV and posting text to prevent confusion, and letting users choose how
much detail they see ([arXiv 2410.00654](https://arxiv.org/html/2410.00654)).

Consequence: the match meter stops being a bare number with component bars. It
states, in sentences, which of *your* skills it found in *this* posting, which
it did not, and what dragged the score down — every claim traceable to a line
in one document or the other.

### On what job seekers actually say

**The ATS panic is largely misplaced, and score-chasing makes résumés worse.**
The community consensus on ATS checkers: a recruiter in the thread puts it
bluntly — "ATS do not scan resumes, nor do they block candidates. They are
electronic file cabinets that us recruiters use to sort resumes." Users report
the same résumé scoring 50–60% on one tool and near-clean on another, and
suspect scores are deflated to sell upgrades. What they actually recommend is
checking *parsability*, keeping one column, and applying early
([VisualCV / Reddit](https://www.visualcv.com/blog/do-ats-checkers-actually-help-reddit/)).

Consequence: this app must not invent an "ATS score". A match score against
*your own* profile is an honest thing to show. A number purporting to predict
what an employer's software will do is not, and chasing it produces the keyword
stuffing that Workday, Greenhouse and Lever now actively flag
([Resume Optimizer Pro](https://resumeoptimizerpro.com/blog/ats-friendly-resume-tips)).

**The frustrations are consistent across communities.** Spam and fake postings,
ghost jobs, remote roles that turn out to be hybrid, and sub-2% response rates.
The features people ask for: vetted listings, filtering for genuinely fresh
postings, salary transparency, and quality over volume
([Reddit round-up](https://bestjobsearchapps.com/articles/en/best-job-boards-reddit-recommends-in-2026-top-picks-from-rjobs-rcscareerquestions-more)).

**Volume is the wrong strategy anyway.** *What Color Is Your Parachute?* is
blunt that "it's a bad idea to mass-apply for job openings," and names the
mismatch driving it: candidates optimise for saving time, employers optimise
for reducing risk — which is why referrals and internal hires win
([summary](https://readingraphics.com/book-summary-what-color-is-your-parachute/)).

Consequence: a short, well-explained list beats a long one. The scoring should
be willing to leave the list small.

### On stale, ghost and junk postings

**Roughly one posting in three is a ghost job.** US employers posted 7.4m
openings against 5.2m hires in June 2025, and fewer than half of October 2024
postings were filled within six months, against 91% in 2019. Detectable
signals: age (over ~30 days suspect, 2–3 months strongly so), generic titles,
evergreen reposting ([Built In](https://builtin.com/articles/ghost-jobs)).

**Disappearing is not the same as closing.** A posting can vanish because the
employer closed it, paused it, hit the 30-day free-listing window, or ran out
of sponsored budget — the last two leave the role genuinely open. Roles
routinely reappear days later under a new URL, and 4.8% of active Indeed
postings cycle three or more times with 10+ day gaps. The reliable signals are
HTTP 404/410 on the posting URL and temporal tracking across scans, not a
single absence ([jobspipe](https://jobspipe.dev/blog/job-closed-or-expired-indeed)).

Consequence: two consecutive misses before closing, and a re-listing reopens
the job rather than being treated as a new one.

**Text-detectable junk signals.** Age over 30 days, vague or over-broad role
descriptions, "unicorn" requirement lists, very short application windows, the
role absent from the company's own site, and the same posting republished
repeatedly ([scam checklist](https://jobsearchwithai.substack.com/p/one-useful-thing-the-job-seeker-scam)).

**Prior art on filtering.** JobFunnel offered `max_listing_days` and a
`company_block_list` and nothing cleverer — and was archived in December 2025
after boards escalated anti-automation
([JobFunnel](https://github.com/PaulMcInnis/JobFunnel)). Scrapers break
constantly: endpoint churn, rate limits, schema drift, LinkedIn rate-limiting
around page 10 per IP ([Scrapfly](https://scrapfly.io/blog/posts/best-open-source-job-scrapers)).
That fragility is exactly why a single missed scan must never close a job.

### On dedupe and taxonomy

**Dedupe on a composite key, and merge rather than discard.** Normalise
aggressively, key on title *and* company with location as the tiebreaker, strip
tracking parameters from URLs, and watch the merge rate — 10–15% is healthy,
much higher means the normalisation is too loose
([dev.to](https://dev.to/get_anything/the-same-job-is-posted-on-three-boards-heres-how-to-deduplicate-job-listings-properly-2862)).
Direct employer postings should supersede aggregator copies of the same role
([job-finder](https://github.com/BenAttanasio/job-finder)).

**There is a free, neutral occupation taxonomy.** O*NET-SOC 2019 has 23 major
groups over 1,016 occupations and is published under CC BY 4.0
([O*NET](https://www.onetcenter.org/taxonomy.html)). Major groups are the right
granularity for a category picker: broad enough to stay short, standard enough
to cover every profession, and owned by nobody's résumé.

**Résumé parsing is a heuristics problem, not an AI one.** OpenResume extracts
fields by grouping text into lines, detecting section headers by bold/uppercase
with a keyword fallback, then scoring candidate text items per field (+3 for
letters only, −4 for containing "@" when looking for a name). It is explicit
that this works for single-column English résumés and degrades outside that
([OpenResume](https://www.open-resume.com/resume-parser)) — worth stating
plainly to users rather than letting a bad parse look like a bad match.

---

## The design

### Scoring: everything derives from the résumé

Five components, 100 points. None of them contains an industry, a company or a
job title written into the source.

| Component | Weight | Where the signal comes from |
|---|---|---|
| Skill match | 35 | The user's own skills, matched in the posting with abbreviation and alias handling |
| Role fit | 25 | Token overlap between the posting's title and the user's target + past titles, plus a seniority-band comparison |
| Text similarity | 20 | TF-IDF cosine between the whole résumé and the whole posting |
| Arrangement | 10 | Remote / hybrid / on-site, against what the user said they want |
| Eligibility | 10 | Location and work-authorisation reachability for this user |

Text similarity is what makes the system background-agnostic. It needs no
keyword list, because the résumé *is* the keyword list. A welder's résumé pulls
welding postings to the top by the same mechanism that pulls product postings
up for a product manager.

Seniority is parsed generically — intern, junior, mid, senior, lead, principal,
head, director, VP, C-level — and compared as a distance in bands rather than
against a list of acceptable titles. Two bands up is a stretch; three is a
mismatch. That works for any profession.

**Optional semantic layer.** When Ollama is installed, the text-similarity axis
is computed from embeddings (`all-minilm`, 23M, via `/api/embed`) instead of
TF-IDF, which handles "ML engineer" ≈ "machine learning engineer" that token
overlap misses ([Ollama](https://ollama.com/blog/embedding-models)). The app
must work identically without it, only slightly blunter.

**Scores are versioned.** `SCORE_VERSION` bumps whenever the rubric changes;
any job carrying an older version is rescored on the next scan or on demand.
Saving the profile or the search settings triggers a rescore, so the list
always reflects the current résumé.

**Cold start.** With no résumé uploaded, skills and text similarity have
nothing to work from. Rather than showing everyone a meaningless 40, the app
scores on what it does have — stated target titles, arrangement, location —
marks the score provisional, and says what uploading a résumé would add. This
is the "new user" weakness content-based methods are known for, handled
explicitly rather than hidden.

**Diversity guard.** Content-based scoring converges on near-identical
postings. After ranking, results are lightly diversified so one company or one
repeated title cannot occupy the whole top of the list.

### Explanations: sentences, not a number

Each job carries generated explanation lines, every one traceable to text in
the résumé or the posting:

- *"Matches 6 of your skills, including Kafka, Airflow and dbt."*
- *"Asks for 8+ years; your résumé shows 6."*
- *"Says hybrid in Berlin — you asked for remote only."*
- *"Posted 47 days ago and reposted twice."*

The component breakdown stays available underneath for anyone who wants it.
What is **not** shown is an "ATS score" — the app does not claim to predict
what an employer's software will do, because the tools that do claim it
disagree wildly with each other and push people toward keyword stuffing.

### Quality signals, surfaced not enforced

Postings are flagged, never silently dropped, for: age over 30 days, three or
more sightings under different URLs, no salary anywhere in the text, an
unusually generic description, and a company on the user's block list. A
`company_block_list` and a `max_age_days` setting give the user the blunt
instruments too.

### Categories: the user chooses, not the code

`backend/taxonomy.py` carries the 23 O*NET-SOC major groups with keyword seeds.
Every job is classified at ingest and stores its category. Settings then offers
two lists:

- **Show** — categories that appear in the list.
- **Exclude from scan** — categories dropped at ingest and never stored at all.

The difference matters. Excluding is for the accountant who never wants to see
a software role again; hiding is for temporarily narrowing the view.

### Closed jobs: retired, not hidden

A posting is closed when it has been missing from **two consecutive scans**,
and only when the board it came from actually succeeded in those scans. One
rate-limited board must never close a column of live jobs — the boards this app
reads do rate-limit, and the single-scan rule would have made that a weekly
event.

Closed jobs stay visible in the Closed column with the reason and date shown.
Nothing is deleted. If a board lists the role again, it reopens.

Separately, postings older than 30 days carry a **stale** badge rather than
being closed, since age is the main honest ghost-job signal but is not proof.

### Dedupe fixes

Titles are stripped of board boilerplate (`[Remote]`, `(100% Remote)`) before
keying; URLs are compared with tracking parameters removed; and the fuzzy
title+company comparison now requires compatible locations, so two cities'
versions of the same role stay separate. The dismissed blocklist uses the
stricter comparison too.

---

## Sources

**Matching technique**

- [How Resume Matching Algorithms Actually Work — Resume Matcher](https://resumematcher.fyi/blog/how-resume-matching-algorithms-actually-work)
- [ResumeIQ — classical-NLP résumé/JD scoring](https://github.com/smitthakkar11/ResumeIQ)
- [Aggarwal, *Recommender Systems: The Textbook* — content-based chapter](https://link.springer.com/book/10.1007/978-3-319-29659-3)
- [AI-driven semantic similarity job matching framework — ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0020025525008643)
- [esco-skill-extractor — embedding thresholds for skills and occupations](https://github.com/KonstantinosPetrakis/esco-skill-extractor)
- [Embedding models — Ollama](https://ollama.com/blog/embedding-models)

**Explainability**

- [Explainable person–job recommendations — Frontiers in AI](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1660548/full)
- [Explainable Multi-Stakeholder Job Recommender Systems — arXiv](https://arxiv.org/html/2410.00654)

**What job seekers report**

- [Do ATS Checkers Actually Help? Reddit insights — VisualCV](https://www.visualcv.com/blog/do-ats-checkers-actually-help-reddit/)
- [Best job boards Reddit recommends — r/jobs, r/cscareerquestions round-up](https://bestjobsearchapps.com/articles/en/best-job-boards-reddit-recommends-in-2026-top-picks-from-rjobs-rcscareerquestions-more)
- [*What Color Is Your Parachute?* — method summary](https://readingraphics.com/book-summary-what-color-is-your-parachute/)
- [ATS Resume Best Practices 2026 — Resume Optimizer Pro](https://resumeoptimizerpro.com/blog/ats-friendly-resume-tips)

**Ghost jobs, staleness and junk**

- [Ghost Jobs: What Are They and How to Spot Them — Built In](https://builtin.com/articles/ghost-jobs)
- [What "job closed or expired" means, and how to detect it — jobspipe](https://jobspipe.dev/blog/job-closed-or-expired-indeed)
- [The Job Seeker Scam Checklist](https://jobsearchwithai.substack.com/p/one-useful-thing-the-job-seeker-scam)

**Pipeline and prior art**

- [Deduplicating job listings properly — dev.to](https://dev.to/get_anything/the-same-job-is-posted-on-three-boards-heres-how-to-deduplicate-job-listings-properly-2862)
- [job-finder — dedupe and profile scoring in practice](https://github.com/BenAttanasio/job-finder)
- [JobFunnel — age filters and block lists (archived Dec 2025)](https://github.com/PaulMcInnis/JobFunnel)
- [Best open-source job scrapers — Scrapfly](https://scrapfly.io/blog/posts/best-open-source-job-scrapers)
- [OpenResume — résumé parser algorithm](https://www.open-resume.com/resume-parser)
- [O*NET-SOC Taxonomy (CC BY 4.0)](https://www.onetcenter.org/taxonomy.html)

O*NET-SOC major group names are used under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), U.S. Department of
Labor, Employment and Training Administration.
