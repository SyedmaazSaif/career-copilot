"""The CV boundary — where Profile facts turn into generated documents.

THE NO-INVENTION RULE (non-negotiable, applies to every generator downstream)
-----------------------------------------------------------------------------
A CV, cover letter, or screener answer may ONLY select, reorder, and reword
content that already exists in the Profile records (see models.py). It may never
add a new claim, metric, employer, job title, date, or skill that is not already
in the Profile.

- Rephrasing must preserve the underlying truth. "Led" stays "led"; it does not
  become "architected" unless the Profile says architected.
- Job titles, employer names, and dates are frozen. Never modify them.
- Every metric in any output must trace back, verbatim, to a Profile record.
- If a job asks for something the Profile does not contain, it is a gap. Note
  the gap; never invent the fact.

Phase 3 builds the generator and a verification pass on top of this module. The
helpers below are the single place that knowledge lives, so every generator and
every check imports from here rather than re-stating the rule.
"""
from __future__ import annotations

from dataclasses import dataclass, field


NO_INVENTION_RULE = (
    "Generated documents may only select, reorder, and reword facts that already "
    "exist in the Profile. Never add a claim, metric, employer, title, date, or "
    "skill that is not in the Profile. Rephrasing must preserve the truth."
)


@dataclass
class ProfileFacts:
    """The flat set of atomic facts a generator is allowed to draw from.

    Phase 3 will build this from the live Profile records and use it as the
    allow-list for the verification pass. Defined here so the boundary — the
    set of things that are 'true for CV purposes' — has one home.
    """

    companies: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)
    dates: set[str] = field(default_factory=set)
    bullet_texts: list[str] = field(default_factory=list)
    skills: set[str] = field(default_factory=set)
    metrics: set[str] = field(default_factory=set)


class InventionError(ValueError):
    """Raised when generated content asserts something not traceable to Profile."""


def assert_traceable(claim: str, facts: ProfileFacts) -> None:
    """Placeholder for the Phase 3 verification pass.

    Phase 3 replaces the body with real fact-diffing that flags any claim not
    grounded in `facts`. It lives here, at the boundary, on purpose: every
    generator must route claims through this gate before a pack is usable.
    """
    raise NotImplementedError(
        "Verification pass is implemented in Phase 3 (CV revamp engine)."
    )
