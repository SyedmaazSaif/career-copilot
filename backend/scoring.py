"""Deterministic job scoring and requirement extraction. No API, no LLM.

A job is scored 0-100 against the Profile across five weighted components, and
carries a reason breakdown plus red flags. The logic follows the scoring
philosophy: cast a wide net across PM/partnerships/growth roles, reward domain
overlap (voice AI, telco, fintech, emerging markets), and penalise
senior-IC-engineering, VP+/CPO, pure data science, and US-only authorisation for
an international (non-US) applicant. Tune the keyword lists to your own search.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Profile, Skill

# Component weights sum to 100.
W_SKILLS = 40
W_TITLE = 25
W_REMOTE = 15
W_VISA = 10
W_DOMAIN = 10

# Titles that fit well (scoring philosophy: cast a wide net).
STRONG_TITLE = [
    "product manager", "senior product", "lead product", "principal product",
    "group product", "product owner", "digital product", "platform product",
    "ai product", "genai product", "voice product", "ml product",
    "partnerships", "platform partnerships", "business development",
    "commercial manager", "revenue manager", "monetization", "monetisation",
    "growth manager", "growth product", "go to market", "go-to-market",
    "launch manager", "vas manager",
]
STRETCH_TITLE = ["head of product", "head of partnerships", "director of product"]
WEAK_TITLE = [
    "software engineer", "developer", "backend", "frontend", "full stack",
    "designer", "data scientist", "data engineer", "machine learning engineer",
    "researcher", "account executive", "sales representative", "recruiter",
    "accountant", "customer support",
]
VERY_SENIOR = ["vp ", "vice president", "chief product", "cpo", "svp", "c-level"]

DOMAIN_KEYWORDS = [
    "voice ai", "ivr", "voice", "telco", "telecom", "mno", "mobile operator",
    "vas", "value added service", "emerging market", "genai", "generative ai",
    "fintech", "financial inclusion", "microfinance", "pakistan", "india",
    "mena", "southeast asia", "sea ", "africa", "mobile-first", "mobile first",
    "subscription", "b2b2c", "esports", "gaming",
]

# Requirement lines usually look like these.
_REQ_HINTS = re.compile(
    r"(years|year of|experience|proficien|familiar|degree|bachelor|master|"
    r"mba|must have|required|requirement|you have|you'll need|we're looking|"
    r"strong|proven|track record|ability to|fluent|native|knowledge of)",
    re.I,
)
_SPLIT = re.compile(r"[\n\r•·▪◦‣•]| - |– |\. (?=[A-Z])")


def build_profile_context(db: Session) -> dict:
    from .models import SearchConfig

    profile = db.get(Profile, 1)
    skills = db.scalars(select(Skill)).all()
    config = db.get(SearchConfig, 1)
    preferred = (
        list(config.preferred_arrangements)
        if config and config.preferred_arrangements
        else ["remote", "hybrid", "onsite"]
    )
    return {
        "skills": [s.name.strip() for s in skills if s.name.strip()],
        "title": (profile.title if profile else "") or "",
        "preferred_arrangements": preferred,
    }


def classify_work_type(text: str, location: str) -> str:
    """remote | hybrid | onsite | unknown, from the JD text and location."""
    blob = f"{location} {text}".lower()
    if "hybrid" in blob:
        return "hybrid"
    if (
        "remote" in location.lower()
        or "fully remote" in text
        or "work from anywhere" in text
        or "100% remote" in text
        or "remote" in text
    ):
        return "remote"
    if any(k in text for k in ("on-site", "onsite", "on site", "in office", "in-office")):
        return "onsite"
    return "unknown"


def classify_employment_type(text: str) -> str:
    if "internship" in text or "intern," in text or " intern " in text:
        return "internship"
    if "part-time" in text or "part time" in text:
        return "part-time"
    if any(k in text for k in ("contract", "contractor", "freelance", "temporary", "fixed-term")):
        return "contract"
    if any(k in text for k in ("full-time", "full time", "permanent")):
        return "full-time"
    return "unknown"


def _arrangement_score(work_type: str, preferred: list[str]) -> tuple[int, str]:
    if work_type == "unknown":
        return round(W_REMOTE * 0.6), "unknown"
    if work_type in preferred:
        return W_REMOTE, work_type
    return round(W_REMOTE * 0.25), work_type


def extract_requirements(description: str, limit: int = 12) -> list[str]:
    """Pull the requirement-like lines out of a JD, deterministically."""
    if not description:
        return []
    text = re.sub(r"<[^>]+>", " ", description)  # strip any stray html
    parts = [p.strip(" \t-–•*") for p in _SPLIT.split(text)]
    reqs: list[str] = []
    seen = set()
    for p in parts:
        if not (18 <= len(p) <= 240):
            continue
        if not _REQ_HINTS.search(p):
            continue
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        reqs.append(p)
        if len(reqs) >= limit:
            break
    return reqs


# Words too generic to signal a real skill match on their own.
_SKILL_STOP = {
    "and", "the", "of", "for", "with", "design", "data", "product", "management",
    "modeling", "analysis", "planning", "development", "strategy", "digital",
}


def _skill_tokens(skill: str) -> tuple[str, str]:
    """Return (full phrase, primary token) for matching a skill in JD text."""
    phrase = skill.lower().split(" (")[0].strip()
    words = [w for w in re.split(r"[^a-z0-9]+", phrase) if len(w) >= 4]
    distinctive = [w for w in words if w not in _SKILL_STOP]
    primary = max(distinctive, key=len) if distinctive else (words[0] if words else "")
    return phrase, primary


def _skill_score(text: str, skills: list[str]) -> tuple[int, list[str]]:
    """A full-phrase hit is a strong signal (weight 1.0); a primary-token hit is
    weaker (0.5). This keeps the axis discriminating instead of saturating."""
    weighted = 0.0
    matched = []
    for s in skills:
        phrase, primary = _skill_tokens(s)
        if len(phrase) < 3:
            continue
        if phrase in text:
            weighted += 1.0
            matched.append(s)
        elif primary and primary in text:
            weighted += 0.5
            matched.append(s)
    # ~7 weighted profile-skill hits earns the full weight.
    score = round(min(weighted / 7.0, 1.0) * W_SKILLS)
    return score, matched[:12]


def _title_score(title: str, text: str) -> tuple[int, str, list[str]]:
    t = title.lower()
    flags: list[str] = []
    if any(k in t for k in VERY_SENIOR):
        flags.append("Very senior (VP/CPO) role — likely needs 12+ years")
        return round(W_TITLE * 0.3), "very senior", flags
    if any(k in t for k in WEAK_TITLE):
        flags.append("Reads as an IC/eng/other track, not product/partnerships")
        return round(W_TITLE * 0.2), "off-track", flags
    if any(k in t for k in STRONG_TITLE):
        return W_TITLE, "strong fit", flags
    if any(k in t for k in STRETCH_TITLE):
        return round(W_TITLE * 0.7), "stretch (head-of)", flags
    return round(W_TITLE * 0.45), "ambiguous", flags


def _visa_score(text: str, location: str) -> tuple[int, str, list[str]]:
    loc = location.lower()
    flags: list[str] = []
    us_only = (
        "us citizen" in text or "u.s. citizen" in text or "green card" in text
        or "security clearance" in text or "must be authorized to work in the us" in text
        or "authorized to work in the united states" in text
    )
    no_sponsor = "no visa sponsorship" in text or "not provide sponsorship" in text or "without sponsorship" in text
    country_locked = bool(
        re.search(r"must (be )?(based|located|reside) in", text)
    ) and "anywhere" not in text
    if us_only:
        flags.append("US work authorization / clearance required")
        return 0, "US-only", flags
    if country_locked:
        flags.append("Requires being based in a specific country")
        return round(W_VISA * 0.3), "country-locked", flags
    if no_sponsor:
        flags.append("No visa sponsorship offered")
        return round(W_VISA * 0.5), "no sponsorship", flags
    if "worldwide" in text or "anywhere" in loc or "global" in text:
        return W_VISA, "global", flags
    return round(W_VISA * 0.7), "open", flags


def _domain_score(text: str) -> tuple[int, list[str]]:
    matched = [k for k in DOMAIN_KEYWORDS if k in text]
    # Each hit is worth ~2.5, capped at the weight.
    score = round(min(len(matched) * 2.5, W_DOMAIN))
    # de-duplicate near-identical hits for display
    return score, sorted(set(matched))[:8]


def score_job(job: dict, ctx: dict) -> tuple[int, dict, list[str], str, str]:
    text = f"{job.get('title','')} {job.get('description','')} {' '.join(job.get('tags',[]) or [])}".lower()
    location = job.get("location", "") or ""
    preferred = ctx.get("preferred_arrangements") or ["remote", "hybrid", "onsite"]

    work_type = classify_work_type(text, location)
    employment_type = classify_employment_type(text)

    skill_s, matched_skills = _skill_score(text, ctx["skills"])
    title_s, title_label, title_flags = _title_score(job.get("title", ""), text)
    arrange_s, arrange_label = _arrangement_score(work_type, preferred)
    visa_s, visa_label, visa_flags = _visa_score(text, location)
    domain_s, matched_domains = _domain_score(text)

    total = max(0, min(100, skill_s + title_s + arrange_s + visa_s + domain_s))
    red_flags = title_flags + visa_flags
    # On-site is only a red flag if the user does not want on-site roles.
    if work_type == "onsite" and "onsite" not in preferred:
        red_flags.append("On-site role — not in your preferred arrangements")

    reason = {
        "skills": {"score": skill_s, "of": W_SKILLS, "matched": matched_skills},
        "title": {"score": title_s, "of": W_TITLE, "label": title_label},
        "arrangement": {"score": arrange_s, "of": W_REMOTE, "label": arrange_label},
        "visa": {"score": visa_s, "of": W_VISA, "label": visa_label},
        "domain": {"score": domain_s, "of": W_DOMAIN, "matched": matched_domains},
    }
    return total, reason, red_flags, work_type, employment_type
