"""Best-effort salary parsing.

Job boards rarely expose a structured salary, so we scrape it out of the free
text. The result is an *estimate* normalized to annual USD, used only for a soft
min-salary filter — jobs with no detectable salary are marked unknown, never
dropped. This is intentionally forgiving: a rough number beats none.
"""
from __future__ import annotations

import re

# Rough FX to USD. Estimates for filtering only, not accounting.
_FX = {
    "USD": 1.0,
    "GBP": 1.27,
    "EUR": 1.08,
    "CAD": 0.73,
    "AUD": 0.66,
    "INR": 0.012,
    "PKR": 0.0036,
    "AED": 0.27,
    "SGD": 0.74,
}

# Symbol / code -> currency. Order matters for the alternation below.
_CUR_TOKENS = [
    ("us$", "USD"), ("usd", "USD"), ("c$", "CAD"), ("cad", "CAD"),
    ("a$", "AUD"), ("aud", "AUD"), ("aed", "AED"), ("sgd", "SGD"),
    ("gbp", "GBP"), ("eur", "EUR"), ("inr", "INR"), ("pkr", "PKR"),
    ("rs.", "PKR"), ("rs", "PKR"), ("$", "USD"), ("£", "GBP"),
    ("€", "EUR"), ("₹", "INR"),
]
_CUR_MAP = dict(_CUR_TOKENS)
_CUR_ALT = "|".join(re.escape(tok) for tok, _ in _CUR_TOKENS)

# Period multipliers to annual.
_PERIOD_MULT = {
    "hour": 2080, "hr": 2080, "/h": 2080,
    "day": 260, "daily": 260,
    "week": 52, "wk": 52, "weekly": 52,
    "month": 12, "mo": 12, "monthly": 12,
    "year": 1, "yr": 1, "annum": 1, "annual": 1, "pa": 1, "p.a": 1,
}

_NUM = r"\d[\d,]*(?:\.\d+)?"
# currency then number(s): "$120k", "£90,000 - £110,000", "PKR 500,000/month"
_CUR_FIRST = re.compile(
    r"(?P<cur>" + _CUR_ALT + r")\s*"
    r"(?P<n1>" + _NUM + r")\s*(?P<k1>k|m)?"
    r"(?:\s*(?:-|–|—|to)\s*(?:" + _CUR_ALT + r")?\s*"
    r"(?P<n2>" + _NUM + r")\s*(?P<k2>k|m)?)?",
    re.I,
)
# number then currency code: "120k USD", "90,000 EUR per year"
_NUM_FIRST = re.compile(
    r"(?P<n1>" + _NUM + r")\s*(?P<k1>k|m)?"
    r"(?:\s*(?:-|–|—|to)\s*(?P<n2>" + _NUM + r")\s*(?P<k2>k|m)?)?"
    r"\s*(?P<cur>usd|gbp|eur|cad|aud|aed|sgd|inr|pkr)",
    re.I,
)


def _to_number(raw: str, suffix: str | None) -> float | None:
    try:
        val = float(raw.replace(",", ""))
    except ValueError:
        return None
    if suffix:
        s = suffix.lower()
        if s == "k":
            val *= 1_000
        elif s == "m":
            val *= 1_000_000
    return val


def _detect_period(text: str, start: int, end: int) -> int:
    """Find a pay period near the matched salary; default annual (1)."""
    window = text[max(0, start - 20) : min(len(text), end + 20)].lower()
    for token, mult in _PERIOD_MULT.items():
        if token in window:
            return mult
    return 1


def parse_salary(text: str) -> dict | None:
    """Return {min, max, currency, text} in annual USD, or None if not found.

    `min`/`max` are integer annual-USD estimates (equal when a single figure).
    """
    if not text:
        return None
    # "401(k)" / "401k" retirement plans are not salaries — neutralize them.
    cleaned = re.sub(r"401\s*\(?\s*k\)?", " ", text, flags=re.I)

    for pattern in (_CUR_FIRST, _NUM_FIRST):
        for m in pattern.finditer(cleaned):
            cur_raw = (m.group("cur") or "").lower()
            currency = _CUR_MAP.get(cur_raw) or {
                "usd": "USD", "gbp": "GBP", "eur": "EUR", "cad": "CAD",
                "aud": "AUD", "aed": "AED", "sgd": "SGD", "inr": "INR",
                "pkr": "PKR",
            }.get(cur_raw)
            if not currency:
                continue
            n1 = _to_number(m.group("n1"), m.group("k1"))
            if n1 is None:
                continue
            n2 = _to_number(m.group("n2"), m.group("k2")) if m.group("n2") else None
            period = _detect_period(cleaned, m.start(), m.end())
            fx = _FX.get(currency, 1.0)

            def annualize(v: float) -> int:
                return int(round(v * period * fx))

            lo = annualize(n1)
            hi = annualize(n2) if n2 is not None else lo
            if hi < lo:
                lo, hi = hi, lo
            # sanity: ignore absurd or trivial figures (bad parses)
            if hi < 1000 or hi > 5_000_000:
                continue
            return {
                "min": lo,
                "max": hi,
                "currency": currency,
                "text": m.group(0).strip(),
            }
    return None
