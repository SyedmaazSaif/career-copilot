"""Job relevance scoring, derived entirely from the user's own résumé.

Nothing in this module names an industry, a company or a job title. That is the
point: career-copilot is for anyone, so a welder, a staff nurse and a tax
accountant have to get good matches out of the same code as a product manager.
The résumé is the keyword list.

The design note in docs/MATCHING.md explains the evidence behind the weights,
the explanation format, and the decisions that are easy to get wrong. Read it
before changing anything here.

Five components, 100 points:

    skills        35   the user's own skills, found in the posting
    role fit      25   title overlap plus a seniority-band comparison
    text          20   TF-IDF cosine between the whole résumé and the posting
    arrangement   10   remote / hybrid / on-site against what they asked for
    eligibility   10   can this person actually take this job, where they are

Every component returns the evidence it used, so the UI can say "matches 6 of
your skills, including Kafka and dbt" rather than showing a bare number. Users
trust a sentence grounded in their own documents; they do not trust a score.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Bullet, Education, Experience, Profile, SearchConfig, Skill
from .title_expansions import expand_titles

# Bump when the rubric changes; jobs carrying an older version get rescored on
# the next app start. 4: arrangement and eligibility stopped being flat additive
# points and instead lift a job in proportion to how well it already matches,
# and role fit stopped awarding free points when there is no title to compare.
SCORE_VERSION = 4

W_SKILLS = 35
W_ROLE = 25
W_TEXT = 20
W_ARRANGEMENT = 10
W_ELIGIBILITY = 10

# ---------------------------------------------------------------------------
# Text utilities. Stdlib only -- no sklearn, no numpy. This runs on a laptop
# alongside everything else and must never be the reason a scan is slow.
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")

# Words that carry no signal about fit. Kept deliberately short: an aggressive
# stop list starts deleting real vocabulary from professions nobody on the
# project thought about.
_STOP = {
    "the", "and", "for", "with", "you", "our", "are", "will", "this", "that",
    "have", "has", "from", "your", "their", "they", "them", "who", "was", "were",
    "but", "not", "all", "any", "can", "may", "should", "would", "could",
    "job", "role", "work", "working", "team", "teams", "company", "position",
    "opportunity", "candidate", "candidates", "applicant", "apply", "please",
    "we", "us", "is", "to", "of", "in", "on", "at", "as", "by", "an", "or",
    "be", "it", "its", "if", "a", "i", "about", "into", "per", "via", "also",
    "more", "most", "other", "some", "such", "than", "then", "there", "these",
    "what", "when", "where", "which", "while", "how", "each", "up", "out",
    "new", "help", "make", "using", "use", "well", "including", "include",
    "etc", "must", "able", "across", "within", "over", "under", "between",
}


def tokenize(text: str) -> list[str]:
    return [
        w
        for w in _WORD.findall((text or "").lower())
        if len(w) > 2 and w not in _STOP
    ]


def _tf(tokens: list[str]) -> dict[str, float]:
    """Sublinear term frequency. Raw counts let one repeated word dominate a
    long job description; log damping is the standard fix."""
    counts = Counter(tokens)
    return {t: 1.0 + math.log(c) for t, c in counts.items()}


def cosine_tfidf(a_tokens: list[str], b_tokens: list[str]) -> float:
    """Cosine similarity of two documents under TF-IDF, with IDF computed over
    the pair itself.

    With only two documents there is no corpus to learn IDF from, so a term
    appearing in both gets weight 1.0 and a term in only one gets ~1.7. That is
    crude but it does the job asked of it: reward shared vocabulary, and do not
    let boilerplate present in every posting carry the score.
    """
    if not a_tokens or not b_tokens:
        return 0.0
    a_tf, b_tf = _tf(a_tokens), _tf(b_tokens)
    a_set, b_set = set(a_tf), set(b_tf)

    def idf(term: str) -> float:
        df = (term in a_set) + (term in b_set)
        return math.log(1 + 2 / df)

    shared = a_set & b_set
    if not shared:
        return 0.0
    dot = sum(a_tf[t] * b_tf[t] * idf(t) ** 2 for t in shared)
    a_norm = math.sqrt(sum((a_tf[t] * idf(t)) ** 2 for t in a_set))
    b_norm = math.sqrt(sum((b_tf[t] * idf(t)) ** 2 for t in b_set))
    if a_norm == 0 or b_norm == 0:
        return 0.0
    return dot / (a_norm * b_norm)


# ---------------------------------------------------------------------------
# Seniority. Parsed as a band rather than matched against a list of acceptable
# titles, so it works for any profession.
# ---------------------------------------------------------------------------

# Only explicit seniority *modifiers* belong here -- never occupation nouns.
#
# An earlier version listed "analyst", "engineer", "officer" and "manager" as
# seniority markers, which produced nonsense the moment it left tech: "Staff
# Nurse" was read as lead level (it is a base-grade RN post), "Junior Data
# Analyst" came out as mid because "analyst" outranked "junior", and every
# "Senior X Manager" was promoted a band by the word manager. Occupation words
# say what the job is, not how senior it is, and what they imply about rank
# differs by profession. "Staff" is deliberately absent for the same reason: a
# staff engineer is senior, a staff nurse is not.
#
# A title with no explicit modifier returns (None, None), which the caller
# treats as unknown and neither rewards nor punishes.
SENIORITY_BANDS: list[tuple[str, int, tuple[str, ...]]] = [
    ("intern", 0, ("intern ", "internship", "trainee", "apprentice", "placement")),
    ("entry", 1, ("junior", "jr ", "jr.", "entry level", "entry-level", "graduate ")),
    ("mid", 2, ("mid level", "mid-level", "intermediate")),
    ("senior", 3, ("senior", "snr ", "sr ", "sr.")),
    # "lead " with the trailing space, so "leadership" does not count as one.
    ("lead", 4, ("lead ", "principal", "supervising", "supervisor")),
    ("head", 5, ("head of", "director", "chief of staff")),
    ("exec", 6, ("vp ", "vp,", "vice president", "svp", "evp", "chief ",
                 "cto", "ceo", "cfo", "coo", "cpo", "cmo")),
]


def seniority_band(title: str) -> tuple[str, int] | tuple[None, None]:
    """Highest band whose explicit modifier appears in the title.

    Returns (None, None) when the title states no seniority, which is the
    honest answer for most job titles outside office work.
    """
    # Punctuation becomes whitespace so "Team Lead, Logistics" and
    # "Lead (Nights)" match the same markers as "Team Lead Logistics". The "."
    # in "Sr." and "Jr." is kept, since those markers include it.
    t = " " + re.sub(r"[^a-z0-9.]+", " ", (title or "").lower()).strip() + " "
    found: tuple[str, int] | None = None
    for name, level, markers in SENIORITY_BANDS:
        if any(m in t for m in markers):
            if found is None or level > found[1]:
                found = (name, level)
    return found if found else (None, None)


# ---------------------------------------------------------------------------
# Skills. Matched with abbreviation handling, because a posting saying "SEO"
# and a résumé saying "Search Engine Optimization" are the same skill.
# ---------------------------------------------------------------------------

_PAREN = re.compile(r"\(([^)]{2,10})\)")


def skill_forms(skill: str) -> list[str]:
    """Every string that should count as a mention of this skill.

    "Search Engine Optimization (SEO)" yields the full phrase, "seo", and the
    initialism "seo" built from the words -- so it matches whichever form the
    posting used. Single generic words are dropped: a skill called "Design"
    would otherwise match nearly every posting ever written.
    """
    s = (skill or "").strip().lower()
    if not s:
        return []
    forms: set[str] = set()

    for abbrev in _PAREN.findall(s):
        if len(abbrev) >= 2:
            forms.add(abbrev.strip())
    base = _PAREN.sub("", s).strip()
    if base:
        forms.add(base)

    words = [w for w in re.split(r"[^a-z0-9+#]+", base) if w]
    # Build the initialism only for genuinely multi-word skills.
    if len(words) >= 2:
        initials = "".join(w[0] for w in words)
        if len(initials) >= 3:
            forms.add(initials)

    # A one-word skill shorter than 3 characters is too noisy to match on.
    return [f for f in forms if len(f) >= 3]


# Skill words too generic to carry a match on their own. A skill called
# "Metal Fabrication" should not be credited to a posting that merely says
# "management".
_GENERIC_SKILL_WORDS = {
    "management", "managing", "skills", "experience", "knowledge", "ability",
    "strong", "good", "excellent", "advanced", "basic", "general", "professional",
    "systems", "system", "tools", "software", "services", "service", "support",
}


# Single words too common to mean anything on their own. A skill listed as
# "Data & Experimentation" must not count as matched because a posting said
# "data" -- nearly every posting does.
_GENERIC_ALONE = {
    "data", "product", "products", "business", "team", "teams", "work",
    "project", "projects", "system", "systems", "service", "services",
    "communication", "management", "technology", "quality", "customer",
    "strategy", "process", "planning", "operations", "development", "design",
    "analysis", "reporting", "research", "support", "delivery", "discovery",
}

_SPLIT_SKILL = re.compile(r"\s*(?:&|/|\band\b|,|\+|\|)\s*", re.I)


def skill_parts(skill: str) -> list[str]:
    """Break a composite skill into the pieces a posting might actually name.

    Profiles very often list skills as headings rather than atoms -- "Growth &
    Monetization", "Cross-Functional & External Partners", "AI & GenAI
    Products". No job description ever contains those strings, so matching them
    whole scores zero for everyone and wastes the largest component of the
    score. Splitting on "&", "/", "and" and commas turns each heading into
    terms that do appear in real postings.
    """
    raw = (skill or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in _SPLIT_SKILL.split(raw) if p.strip()]
    kept: list[str] = []
    for part in parts:
        words = [w for w in re.split(r"[^a-z0-9+#]+", part.lower()) if w]
        # A one-word piece has to carry real meaning by itself.
        if len(words) == 1:
            w = words[0]
            if len(w) < 4 or w in _GENERIC_ALONE or w in _STOP:
                continue
        kept.append(part)
    # If splitting left nothing usable, fall back to the original so a skill is
    # never silently dropped.
    return kept or [raw]


def _skill_hit(skill: str, padded_text: str, text_tokens: set[str]) -> float:
    """How strongly this skill appears in the posting: 1.0 exact, 0.6 partial, 0 absent.

    Exact is the whole phrase (or its abbreviation) appearing as written.
    Partial is every distinctive word of a multi-word skill appearing
    somewhere, which is how postings usually write them: a résumé saying "MIG
    Welding" against a posting saying "MIG and TIG welding" is a real match
    that phrase-only matching misses, and those misses were showing up in the
    explanations as skills the posting supposedly did not want.
    """
    best = 0.0
    for part in skill_parts(skill):
        best = max(best, _part_hit(part, padded_text, text_tokens))
        if best >= 1.0:
            return 1.0
    return best


def _part_hit(skill: str, padded_text: str, text_tokens: set[str]) -> float:
    """How strongly one atomic skill term appears in the posting."""
    forms = skill_forms(skill)
    if not forms:
        return 0.0
    for form in forms:
        if f" {form} " in padded_text or f" {form}," in padded_text or f" {form}." in padded_text:
            return 1.0

    # Three characters, not four: the distinctive word in a skill is often a
    # short acronym -- MIG, TIG, SQL, AWS, CDL, RN -- and a four-character floor
    # threw those away, which is why "MIG Welding" read as absent from a posting
    # that opened with "MIG and TIG welding".
    words = [
        w for w in re.split(r"[^a-z0-9+#]+", (skill or "").lower())
        if len(w) >= 3 and w not in _GENERIC_SKILL_WORDS and w not in _STOP
    ]
    # Only multi-word skills get the partial path. A single generic word
    # matching loosely is how the old scorer gave half credit to everything.
    if len(words) >= 2 and all(w in text_tokens for w in words):
        return 0.6
    return 0.0


def _skills_component(
    job_text: str,
    skills: list[str],
    skill_weights: dict[str, float] | None = None,
) -> tuple[int, list[str], list[str]]:
    """Returns (score, skills found in the posting, skills not found).

    Skills are weighted by where they appear in the résumé (a headline skill
    counts more than one buried in the skills list alone)."""
    if not skills:
        return 0, [], []
    weights = skill_weights or {}
    padded = f" {job_text} "
    tokens = set(tokenize(job_text))

    matched: list[str] = []
    missing: list[str] = []
    matched_weight = 0.0
    total_weight = 0.0
    for skill in skills:
        if not skill_forms(skill):
            continue
        w = max(0.5, min(weights.get(skill, 1.0), 2.0))
        total_weight += w
        hit = _skill_hit(skill, padded, tokens)
        if hit:
            matched_weight += hit * w
            matched.append(skill)
        else:
            missing.append(skill)

    if not total_weight:
        return 0, [], []
    # Proportional to how much of the user's skill set the posting asks for. A
    # posting cannot name every skill a person has, so 60% weighted coverage is
    # already a full-marks match rather than requiring an impossible 100%.
    ratio = matched_weight / total_weight
    score = round(min(ratio / 0.6, 1.0) * W_SKILLS)
    return score, matched, missing


# Words that describe a job's SHAPE or RANK rather than its trade. Two titles
# sharing only these have nothing in common: "Senior Marketing Manager" and
# "Senior Product Manager" overlap on "senior" and "manager" and are completely
# different jobs, which is exactly how a marketing role ended up scoring the
# same as a product role. Seniority is already scored separately, by band.
#
# Occupation nouns stay OUT of this list on purpose -- engineer, analyst, nurse,
# welder, designer, accountant all identify a trade and must still count.
_GENERIC_TITLE_WORDS = {
    "senior", "junior", "lead", "principal", "staff", "head", "chief",
    "director", "vice", "president", "associate", "assistant", "intern",
    "trainee", "manager", "management", "specialist", "officer", "executive",
    "coordinator", "supervisor", "mid", "level", "entry", "experienced",
    "remote", "hybrid", "onsite", "full", "part", "time", "contract",
    "permanent", "temporary", "freelance", "consultant", "global", "regional",
}


def _title_terms(title: str) -> set[str]:
    """The words in a title that actually say what the job is."""
    return {w for w in tokenize(title) if w not in _GENERIC_TITLE_WORDS}


def _role_component(
    job_title: str, target_titles: list[str], user_band: int | None
) -> tuple[int, dict]:
    """Title overlap plus seniority distance. No hardcoded title list."""
    jt = _title_terms(job_title)
    if not jt or not target_titles:
        # A title with no meaningful words (or no stated target) is "no
        # signal", not "half a match". Awarding 40% here gave "Contract IT
        # Specialist" ten free points against a welder's profile.
        return 0, {"label": "no title to compare", "overlap": []}

    best_overlap: set[str] = set()
    for target in target_titles:
        overlap = jt & _title_terms(target)
        if len(overlap) > len(best_overlap):
            best_overlap = overlap

    # Two shared meaningful words ("registered nurse", "data engineer") is a
    # strong title signal; one is partial.
    overlap_ratio = min(len(best_overlap) / 2.0, 1.0)
    base = overlap_ratio * (W_ROLE * 0.7)

    band_name, job_band = seniority_band(job_title)
    label = band_name or "unstated"
    if not best_overlap:
        # Seniority only adjusts a title that already overlaps. A job whose
        # title shares nothing with yours earns no seniority credit, however
        # senior it is.
        band_points = 0.0
    elif job_band is not None and user_band is not None:
        gap = job_band - user_band
        if gap <= 0:
            band_points = W_ROLE * 0.3          # at or below your level
        elif gap == 1:
            band_points = W_ROLE * 0.22         # one step up: a stretch
        elif gap == 2:
            band_points = W_ROLE * 0.1
        else:
            band_points = 0.0                   # several levels above
    else:
        band_points = W_ROLE * 0.2              # unknown, neither reward nor punish

    return round(base + band_points), {
        "label": label,
        "overlap": sorted(best_overlap),
        "job_band": band_name,
        "band_gap": (job_band - user_band) if (job_band is not None and user_band is not None) else None,
    }


# ---------------------------------------------------------------------------
# Arrangement and eligibility
# ---------------------------------------------------------------------------

# Ordered: the first pattern that matches wins. "Hybrid" is checked before
# "remote" because hybrid postings almost always say "remote" somewhere too.
_HYBRID = ("hybrid", "days in office", "days per week in the office", "days onsite")
_ONSITE = ("on-site", "onsite", "on site", "in office", "in-office", "in person", "in-person")
_REMOTE_STRONG = (
    "fully remote", "100% remote", "work from anywhere", "remote-first",
    "remote first", "work from home", "telecommute", "distributed team",
)


def classify_work_type(title: str, description: str, location: str) -> str:
    """remote | hybrid | onsite | unknown.

    The previous version returned "remote" whenever the word "remote" appeared
    anywhere in the posting. Nearly every posting mentions it -- "this role is
    not remote", "remote-friendly culture" -- so almost everything scored as
    remote and the whole axis became noise. Now only an unambiguous phrase, or
    the location field itself, counts.
    """
    loc = (location or "").lower()
    text = f"{title or ''} {description or ''}".lower()

    if any(k in loc for k in ("hybrid",)) or any(k in text for k in _HYBRID):
        return "hybrid"
    if "remote" in loc or "anywhere" in loc or "worldwide" in loc:
        return "remote"
    if any(k in text for k in _REMOTE_STRONG):
        return "remote"
    if any(k in text for k in _ONSITE):
        return "onsite"
    # A named city with no remote language is on-site far more often than not,
    # but not reliably enough to assert it.
    return "unknown"


def classify_employment_type(text: str) -> str:
    t = (text or "").lower()
    if "internship" in t or " intern " in t:
        return "internship"
    if "part-time" in t or "part time" in t:
        return "part-time"
    if any(k in t for k in ("contract", "contractor", "freelance", "temporary", "fixed-term")):
        return "contract"
    if any(k in t for k in ("full-time", "full time", "permanent")):
        return "full-time"
    return "unknown"


def _arrangement_component(work_type: str, preferred: list[str]) -> tuple[int, str]:
    if work_type == "unknown":
        return round(W_ARRANGEMENT * 0.6), "not stated"
    if work_type in preferred:
        return W_ARRANGEMENT, work_type
    return round(W_ARRANGEMENT * 0.2), work_type


_MUST_BE_IN = re.compile(r"must (?:be )?(?:based|located|reside|live) in", re.I)

# Region keywords -> canonical region tag. Deliberately no bare "america" for
# the US, so "Latin America" never reads as "US". "us" matches only as a whole
# word, so "focus" or "bonus" never count.
_REGION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\blatin america\b|\blatam\b|\b(?:brazil|mexico|argentina|colombia|chile)\b", re.I), "latam"),
    (re.compile(r"\b(?:us|u\.s\.|usa|united states)\b", re.I), "us"),
    (re.compile(r"\b(?:uk|u\.k\.|united kingdom|britain|england|scotland|wales)\b", re.I), "europe"),
    (re.compile(r"\b(?:europe|eu|emea)\b", re.I), "europe"),
    (re.compile(r"\b(?:germany|france|netherlands|spain|italy|ireland|poland|sweden|portugal|switzerland|austria|belgium|denmark|finland|norway)\b", re.I), "europe"),
    (re.compile(r"\b(?:apac|asia|asia-pacific)\b", re.I), "apac"),
    (re.compile(r"\b(?:australia|new zealand|singapore|india|japan|china|hong kong|malaysia|indonesia|philippines|pakistan|bangladesh|sri lanka)\b", re.I), "apac"),
    (re.compile(r"\bcanada\b", re.I), "canada"),
    (re.compile(r"\b(?:middle east|uae|dubai|saudi|qatar|israel)\b", re.I), "emea"),
    (re.compile(r"\b(?:africa|south africa|nigeria|kenya|egypt)\b", re.I), "africa"),
]

_REGION_ONLY = re.compile(
    r"\b(?:us|u\.s\.|usa|uk|u\.k\.|eu|emea|europe|apac|canada|latam|india|australia|united states)\s+only\b",
    re.I,
)


def detect_regions(text: str) -> set[str]:
    """Region tags (us, europe, apac, latam, canada, emea, africa) in text."""
    out: set[str] = set()
    for pat, tag in _REGION_PATTERNS:
        if pat.search(text or ""):
            out.add(tag)
    return out


_YEARS_REQ = re.compile(r"(\d{1,2})\+?\s*(?:years?|yrs?)", re.I)


def _max_years_required(text: str) -> int | None:
    """The largest 'N+ years' requirement mentioned, or None."""
    found = [int(m.group(1)) for m in _YEARS_REQ.finditer(text or "")]
    return max(found) if found else None


def _eligibility_component(
    text: str,
    location: str,
    home_locations: list[str],
    home_regions: set[str],
) -> tuple[int, str, list[str]]:
    loc = (location or "").lower()
    t = (text or "").lower()
    flags: list[str] = []
    combined = f"{loc} {t}"

    at_home = any(h and (h in loc or h in t) for h in home_locations)
    if not at_home and home_regions:
        at_home = bool(home_regions & detect_regions(combined))

    authorization_locked = any(
        k in t
        for k in (
            "us citizen", "u.s. citizen", "green card", "security clearance",
            "must be authorized to work in the us",
            "authorized to work in the united states",
            "eu citizen", "right to work in the uk", "citizens only",
        )
    )
    sponsors = any(
        k in t
        for k in (
            "visa sponsorship", "sponsorship available", "will sponsor",
            "visa available", "we sponsor", "sponsorship offered",
        )
    )
    no_sponsor = any(
        k in t
        for k in (
            "no visa sponsorship", "not provide sponsorship",
            "without sponsorship", "unable to sponsor", "no sponsorship",
        )
    )

    required = detect_regions(combined)
    constrained = (
        bool(_MUST_BE_IN.search(t))
        or bool(_REGION_ONLY.search(t))
        or " time zone" in t
        or " time zones" in t
        or " based in" in t
        or " located in" in t
        or "must reside" in t
        or "must live" in t
    )

    if at_home:
        return W_ELIGIBILITY, "where you are", flags
    if authorization_locked:
        flags.append("Requires citizenship or clearance you may not hold")
        return 0, "authorization required", flags
    if required and constrained:
        flags.append("Requires being based in a specific region or time zone")
        return 0, "location-locked", flags
    if no_sponsor:
        flags.append("No visa sponsorship offered")
        return round(W_ELIGIBILITY * 0.4), "no sponsorship", flags
    if sponsors:
        return W_ELIGIBILITY, "visa sponsorship offered", flags
    if "worldwide" in t or "anywhere" in loc or "globally" in t or "work from anywhere" in t:
        return W_ELIGIBILITY, "open worldwide", flags
    return round(W_ELIGIBILITY * 0.7), "no barrier stated", flags


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def build_profile(db: Session) -> dict:
    """Everything scoring needs, read once per scan rather than per job."""
    profile = db.get(Profile, 1)
    skills = [s.name.strip() for s in db.scalars(select(Skill)).all() if s.name.strip()]
    experiences = db.scalars(select(Experience)).all()
    bullets = db.scalars(select(Bullet)).all()
    education = db.scalars(select(Education)).all()
    config = db.get(SearchConfig, 1)

    # The résumé as one document. This is what makes the scoring work for any
    # background: the vocabulary of the person's actual career is the yardstick.
    parts: list[str] = []
    if profile:
        parts += [profile.title or "", profile.summary or ""]
    parts += [f"{e.role} {e.company} {e.context}" for e in experiences]
    parts += [b.text for b in bullets]
    parts += [f"{ed.degree} {ed.school}" for ed in education]
    parts += skills
    resume_text = " ".join(p for p in parts if p)

    past_titles = [e.role for e in experiences if e.role]
    target_titles = list(config.queries) if config and config.queries else []
    if profile and profile.title:
        target_titles = [profile.title] + target_titles
    # Fall back to what they have done if they have not said what they want.
    if not target_titles:
        target_titles = past_titles
    # Related-title expansion from the editable data file (title_expansions.json),
    # so "Product Manager" also matches Product Owner / Technical PM / etc.
    target_titles = expand_titles(target_titles)

    # Their own seniority: the highest band across current and past titles.
    bands = [
        seniority_band(t)[1]
        for t in ([profile.title] if profile and profile.title else []) + past_titles
    ]
    user_band = max([b for b in bands if b is not None], default=None)

    preferred = (
        list(config.preferred_arrangements)
        if config and config.preferred_arrangements
        else ["remote", "hybrid", "onsite"]
    )
    home_locations = [
        part.strip().lower()
        for raw in ([profile.location] if profile and profile.location else [])
        + list(config.locations or [] if config else [])
        for part in re.split(r"[,/|]", raw)
        if len(part.strip()) >= 3
    ]
    home_regions: set[str] = set()
    for hloc in home_locations:
        home_regions |= detect_regions(hloc)

    # Weight skills by where they appear in the résumé: a skill named in the
    # title or summary counts more than one buried in the skills list alone.
    strong_text = " ".join(
        [profile.title if profile else "", profile.summary if profile else ""]
    ).lower()
    medium_text = " ".join(
        [b.text for b in bullets] + [f"{e.role} {e.context}" for e in experiences]
    ).lower()
    skill_weights: dict[str, float] = {}
    for s in skills:
        w = 1.0
        key = s.lower()
        if key and key in strong_text:
            w += 0.5
        if key and key in medium_text:
            w += 0.25
        skill_weights[s] = min(w, 1.75)

    # Rough years of experience: now minus the earliest year on the CV.
    start_years = [
        int(y)
        for e in experiences
        for y in re.findall(r"\b(?:19|20)\d{2}\b", e.dates or "")
    ]
    years_experience = datetime.now().year - min(start_years) if start_years else None

    return {
        "skills": skills,
        "resume_text": resume_text,
        "resume_tokens": tokenize(resume_text),
        "target_titles": target_titles,
        "user_band": user_band,
        "preferred_arrangements": preferred,
        "home_locations": home_locations,
        "home_regions": home_regions,
        "skill_weights": skill_weights,
        "years_experience": years_experience,
        # Cold start: with no résumé there is nothing to match on, and a score
        # presented as if there were would be a lie.
        "has_resume": bool(skills or resume_text.strip()),
    }


def derive_queries(profile: dict, limit: int = 15) -> list[str]:
    """Search terms for a scan, from the same résumé the scoring uses.

    The old default was a fixed list of product-management titles, which made
    the whole app a product-manager finder: every scan asked boards for
    "product manager" and never for "welder" or "registered nurse", so those
    jobs never entered the database even though the boards had them. Queries
    now come from the profile itself — target titles first, then distinctive
    skills — so a welder's résumé asks for welding roles and a nurse's for
    nursing roles.
    """
    queries: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        term = re.sub(r"[^a-z0-9+# ]", " ", (term or "").lower())
        term = re.sub(r"\s+", " ", term).strip()
        if not term or len(term) < 3 or term in seen or len(term.split()) > 6:
            return
        seen.add(term)
        queries.append(term)

    for title in profile.get("target_titles") or []:
        add(title)
        # "Senior PM — Consumer Platforms" -> also search the core "Senior PM".
        add(re.split(r"\s*[—–|·]\s*", title, 1)[0])

    for skill in profile.get("skills") or []:
        for part in skill_parts(skill):
            words = [
                w for w in tokenize(part)
                if w not in _GENERIC_ALONE and w not in _GENERIC_SKILL_WORDS
            ]
            if words:
                add(" ".join(words))
        if len(queries) >= limit:
            break

    return queries[:limit]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _explain(
    matched: list[str], missing: list[str], role: dict, arrangement: str,
    eligibility: str, work_type: str, preferred: list[str], has_resume: bool,
) -> list[str]:
    """Plain sentences, each traceable to the résumé or the posting.

    Users trust "matches 6 of your skills, including Kafka and dbt" far more
    than a number, and a sentence can be checked against the source; a score
    cannot.
    """
    lines: list[str] = []

    if not has_resume:
        lines.append(
            "Provisional score — upload your résumé and this will be matched "
            "against your actual skills and experience."
        )

    if matched:
        shown = ", ".join(matched[:3])
        extra = f" and {len(matched) - 3} more" if len(matched) > 3 else ""
        lines.append(
            f"Matches {len(matched)} of your skills, including {shown}{extra}."
        )
    elif has_resume:
        lines.append("None of the skills on your résumé appear in this posting.")

    if role.get("overlap"):
        lines.append(
            "Title overlaps with what you're looking for on "
            + ", ".join(role["overlap"][:3])
            + "."
        )
    gap = role.get("band_gap")
    if gap is not None and gap >= 2:
        lines.append(
            f"Listed as {role.get('job_band')} — a couple of levels above your "
            "current title."
        )
    elif gap is not None and gap <= -2:
        lines.append(
            f"Listed as {role.get('job_band')} — more junior than your current title."
        )

    if work_type != "unknown" and work_type not in preferred:
        lines.append(
            f"This is a {work_type} role, and you asked for "
            + " or ".join(preferred)
            + "."
        )

    if eligibility == "authorization required":
        lines.append("Asks for citizenship or a clearance.")
    elif eligibility == "location-locked":
        lines.append("Requires being based somewhere specific.")
    elif eligibility == "no sponsorship":
        lines.append("States that visa sponsorship is not offered.")

    if missing and len(missing) <= 6 and matched:
        lines.append("Doesn't mention: " + ", ".join(missing[:4]) + ".")

    return lines


def score_job(job: dict, profile: dict) -> dict:
    """Score one posting. Returns everything the row and the UI need."""
    title = job.get("title", "") or ""
    description = job.get("description", "") or ""
    location = job.get("location", "") or ""
    tags = " ".join(job.get("tags", []) or [])
    job_text = f"{title} {description} {tags}".lower()

    work_type = classify_work_type(title, description, location)
    employment_type = classify_employment_type(job_text)

    skills_s, matched, missing = _skills_component(
        job_text, profile["skills"], profile.get("skill_weights")
    )
    role_s, role_detail = _role_component(
        title, profile["target_titles"], profile["user_band"]
    )
    text_s = round(
        cosine_tfidf(profile["resume_tokens"], tokenize(f"{title} {description}"))
        * W_TEXT
    )
    arrange_s, arrange_label = _arrangement_component(
        work_type, profile["preferred_arrangements"]
    )
    elig_s, elig_label, elig_flags = _eligibility_component(
        job_text, location, profile["home_locations"], profile.get("home_regions", set())
    )

    if profile["has_resume"]:
        # Arrangement and eligibility answer "can you take this job", not "does
        # this job fit your career". Awarding them flat made any remote,
        # open-worldwide posting start at 20 points before a single skill or
        # title was considered, so a welder saw an engineering manager ranked
        # above real trade roles. They now lift a job in proportion to how well
        # it already matches: full weight at full relevance, nothing at zero.
        fit = skills_s + role_s + text_s
        fit_ratio = fit / (W_SKILLS + W_ROLE + W_TEXT)
        arrange_s = round(arrange_s * fit_ratio)
        elig_s = round(elig_s * fit_ratio)
        total = fit + arrange_s + elig_s
    else:
        # Without a résumé, skills and text similarity are structurally zero.
        # Scoring out of the axes that do work, then scaling, avoids telling
        # everyone their matches are terrible when the app simply has no data.
        available = W_ROLE + W_ARRANGEMENT + W_ELIGIBILITY
        total = round((role_s + arrange_s + elig_s) / available * 100)

    total = max(0, min(100, total))

    red_flags = list(elig_flags)
    if work_type == "onsite" and "onsite" not in profile["preferred_arrangements"]:
        red_flags.append("On-site role — not in your preferred arrangements")
    if profile.get("years_experience") is not None:
        req = _max_years_required(job_text)
        if req and req > profile["years_experience"] + 1:
            red_flags.append(
                f"Asks for {req}+ years of experience (your résumé shows about "
                f"{profile['years_experience']})"
            )

    reason = {
        "skills": {"score": skills_s, "of": W_SKILLS, "matched": matched[:12],
                   "missing": missing[:12]},
        "role": {"score": role_s, "of": W_ROLE, **role_detail},
        "text": {"score": text_s, "of": W_TEXT},
        "arrangement": {"score": arrange_s, "of": W_ARRANGEMENT, "label": arrange_label},
        "eligibility": {"score": elig_s, "of": W_ELIGIBILITY, "label": elig_label},
        "provisional": not profile["has_resume"],
    }

    return {
        "score": total,
        "reason": reason,
        "red_flags": red_flags,
        "work_type": work_type,
        "employment_type": employment_type,
        "explanations": _explain(
            matched, missing, role_detail, arrange_label, elig_label,
            work_type, profile["preferred_arrangements"], profile["has_resume"],
        ),
        "score_version": SCORE_VERSION,
    }
