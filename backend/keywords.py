"""ATS keyword check: which words the job asks for that the profile is missing.

Pure, deterministic text comparison — no AI. Helps the user see the gap between
a job description and what their profile actually says.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Experience, Profile, Skill

STOPWORDS = set(
    """a an and are as at be but by for from has have in into is it its of on or
    that the this to was were will with you your we our they their role work team
    job experience skills years plus etc apply equal opportunity benefits company
    employment full time part remote hybrid onsite based strong ability able
    required requirements must nice have can should may responsibilities we're
    you'll we'll looking join our opportunity about more what when where how all
    any new now out over under also each need needs""".split()
)

_TOKEN = re.compile(r"[a-z][a-z0-9+#./-]{2,}")


def _tokens(text: str) -> list[str]:
    """Ordered, deduped, lowercased tokens that are not stopwords."""
    seen: list[str] = []
    for t in _TOKEN.findall((text or "").lower()):
        t = t.strip(".,:;!?")
        if len(t) < 3:
            continue
        if t not in STOPWORDS and t not in seen:
            seen.append(t)
    return seen


def job_keywords(job) -> list[str]:
    return _tokens(f"{job.title} {job.description}")


def profile_keywords(db: Session) -> set[str]:
    profile = db.get(Profile, 1)
    parts: list[str] = []
    if profile:
        parts += [profile.title, profile.summary]
    for e in db.scalars(select(Experience)).all():
        parts += [e.role, e.context or ""]
        for b in e.bullets:
            parts.append(b.text)
            parts += list(b.skill_tags or [])
    for s in db.scalars(select(Skill)).all():
        parts.append(s.name)
    return set(_tokens(" ".join(p for p in parts if p)))


def _profile_tips(db: Session) -> list[str]:
    tips: list[str] = []
    p = db.get(Profile, 1)
    if not p:
        return tips
    if not p.phone:
        tips.append("Add a phone number to your profile — many ATS screens expect one.")
    if not p.email:
        tips.append("Add an email address to your profile.")
    if not p.summary:
        tips.append("Your profile summary is empty — add 2–3 sentences about what you do.")
    if not p.linkedin:
        tips.append("Add your LinkedIn URL to your profile.")
    return tips


def keyword_gaps(db: Session, job) -> dict:
    want = job_keywords(job)
    have = profile_keywords(db)
    missing = [w for w in want if w not in have]
    total = len(want)
    present = total - len(missing)
    return {
        "missing": missing[:30],
        "present": present,
        "total": total,
        "coverage": round(present / total, 3) if total else None,
        "tips": _profile_tips(db),
    }
