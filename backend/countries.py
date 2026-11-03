"""Derive a canonical country name from a free-text job location.

Python port of src/countries.js. Keep the two in sync when adding countries.
"""
from __future__ import annotations

import re

# Most-specific names first; each entry maps a canonical country to the
# spellings that appear in real job-board locations.
_COUNTRY_ALIASES = [
    ("United States", ["united states", "united states of america", "u.s.a", "u.s.", "usa", "us"]),
    ("United Kingdom", ["united kingdom", "great britain", "britain", "england", "scotland", "uk"]),
    ("United Arab Emirates", ["united arab emirates", "uae", "dubai", "abu dhabi"]),
    ("Australia", ["new south wales", "australia"]),
    ("New Zealand", ["new zealand"]),
    ("South Africa", ["south africa"]),
    ("Saudi Arabia", ["saudi arabia", "saudi"]),
    ("Czech Republic", ["czech republic", "czechia"]),
    ("South Korea", ["south korea"]),
    ("Hong Kong", ["hong kong"]),
    ("Sri Lanka", ["sri lanka"]),
    ("Canada", ["canada"]),
    ("Germany", ["germany"]),
    ("France", ["france"]),
    ("India", ["india"]),
    ("Pakistan", ["pakistan"]),
    ("Brazil", ["brazil"]),
    ("Mexico", ["mexico"]),
    ("Spain", ["spain"]),
    ("Italy", ["italy"]),
    ("Netherlands", ["netherlands", "holland"]),
    ("Sweden", ["sweden"]),
    ("Switzerland", ["switzerland"]),
    ("Singapore", ["singapore"]),
    ("Ireland", ["ireland"]),
    ("Poland", ["poland"]),
    ("Portugal", ["portugal"]),
    ("Romania", ["romania"]),
    ("Denmark", ["denmark"]),
    ("Norway", ["norway"]),
    ("Finland", ["finland"]),
    ("Belgium", ["belgium"]),
    ("Austria", ["austria"]),
    ("Turkey", ["turkey"]),
    ("Japan", ["japan"]),
    ("China", ["china"]),
    ("Indonesia", ["indonesia"]),
    ("Malaysia", ["malaysia"]),
    ("Thailand", ["thailand"]),
    ("Vietnam", ["vietnam"]),
    ("Philippines", ["philippines"]),
    ("Egypt", ["egypt"]),
    ("Nigeria", ["nigeria"]),
    ("Kenya", ["kenya"]),
    ("Argentina", ["argentina"]),
    ("Chile", ["chile"]),
    ("Colombia", ["colombia"]),
    ("Israel", ["israel"]),
    ("Ukraine", ["ukraine"]),
    ("Greece", ["greece"]),
    ("Estonia", ["estonia"]),
    ("Latvia", ["latvia"]),
    ("Lithuania", ["lithuania"]),
    ("Croatia", ["croatia"]),
    ("Bulgaria", ["bulgaria"]),
    ("Hungary", ["hungary"]),
    ("Russia", ["russia"]),
]

_ALIAS_RES = [
    (name, re.compile(rf"(^|[^a-z])({joined})($|[^a-z])"))
    for name, joined in (
        (
            name,
            "|".join(sorted((re.escape(a) for a in aliases), key=len, reverse=True)),
        )
        for name, aliases in _COUNTRY_ALIASES
    )
]


def derive_country(location: str | None) -> str:
    if not location:
        return ""
    s = location.lower()
    for name, re_ in _ALIAS_RES:
        if re_.search(s):
            return name
    return ""
