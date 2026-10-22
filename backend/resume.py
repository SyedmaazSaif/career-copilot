"""Read a resume file and turn it into profile data.

Text extraction is deterministic (pypdf / python-docx). Turning that text into
structured profile records uses the optional local Ollama model when available;
without it, a deterministic heuristic still fills contact details, title, skills,
work experience and education, so an upload is useful even when the local model
is switched off or crashes. No paid API is ever used.

The AI pass is deliberately split into three small, section-scoped calls rather
than one request for the whole schema. A local model on a laptop is slow in
proportion to how much JSON it has to write, and one big call reliably ran past
any sensible timeout. Contact details always come from the regex pass -- an
exact match beats a small model guessing.
"""
from __future__ import annotations

import io
import re

from . import ollama_client

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+", re.I)
URL_RE = re.compile(r"https?://[\w.-]+\.[a-z]{2,}(?:/\S*)?", re.I)

# A bare domain is still a portfolio link on a résumé ("syedmaazsaif.com").
# The negative lookbehind stops it matching the domain half of an email.
_PORTFOLIO_RE = re.compile(
    r"(?<![\w@.-])(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}(?:/\S*)?", re.I
)

# An explicit statement about where the person may work. Regex-owned so the
# local model can never write contact details into this field.
_AUTH_RE = re.compile(
    r"(?:authorized|eligible|entitled) to work (?:in|within)?[^\n|,;]{0,50}"
    r"|right to work (?:in|within)?[^\n|,;]{0,50}"
    r"|(?:us|u\.s\.) (?:citizen|person|permanent resident)"
    r"|green card(?: holder)?"
    r"|work (?:authorization|permit|status)\s*[:：]\s*[^\n|,;]{0,50}",
    re.I,
)

# Fields the regex pass owns outright; the local model never writes them.
# work_authorization is here because the model once returned a LinkedIn URL for
# it and invented salary expectations from revenue figures.
_EXACT_FIELDS = ("email", "phone", "linkedin", "portfolio", "work_authorization")

# The only profile fields the local model may fill from the header. Salary
# expectations and notice period are the user's own preference, not résumé
# facts, so they are deliberately absent from this list.
_AI_PROFILE_FIELDS = ("name", "title", "location", "summary")


def extract_text(filename: str, content: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _pdf_text(content)
    if name.endswith(".docx"):
        return _docx_text(content)
    # plain text fallback
    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _pdf_text(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _docx_text(content: bytes) -> str:
    import docx

    doc = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)


# --- section splitting -----------------------------------------------------

# Heading keyword -> the bucket it opens.
_SECTION_WORDS = {
    "summary": "summary", "profile": "summary", "objective": "summary",
    "about": "summary",
    "experience": "experience", "employment": "experience",
    "work history": "experience", "career": "experience",
    "professional experience": "experience", "work experience": "experience",
    "education": "education", "academic": "education",
    "skills": "skills", "technical skills": "skills", "competencies": "skills",
    "expertise": "skills",
    "certification": "certifications", "certifications": "certifications",
    "courses": "certifications", "training": "certifications",
    "languages": "languages",
}


def _heading_bucket(line: str) -> str | None:
    """Return the section a line opens, or None if it is not a heading."""
    stripped = line.strip().strip(":").strip()
    if not stripped or len(stripped) > 60:
        return None
    # A heading is short and carries no sentence punctuation.
    if any(ch in stripped for ch in ".,;@"):
        return None
    key = stripped.lower()
    if key in _SECTION_WORDS:
        return _SECTION_WORDS[key]
    # Tolerate "PROFESSIONAL EXPERIENCE", "Key Skills", etc.
    if stripped.isupper() or len(stripped.split()) <= 3:
        for word, bucket in _SECTION_WORDS.items():
            if word in key:
                return bucket
    return None


def _split_sections(text: str) -> dict[str, str]:
    """Bucket resume lines by heading. 'header' holds everything before the
    first heading -- normally the name and contact block."""
    buckets: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.splitlines():
        bucket = _heading_bucket(line)
        if bucket:
            current = bucket
            buckets.setdefault(current, [])
            continue
        buckets.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in buckets.items()}


def _section(sections: dict[str, str], *names: str, fallback: str = "") -> str:
    for name in names:
        if sections.get(name):
            return sections[name]
    return fallback


# --- public entry point ----------------------------------------------------

def parse_resume(text: str) -> tuple[dict, bool, str | None]:
    """Return (profile_data, used_ai, error). profile_data is shaped like
    master_profile.yaml. The regex pass always runs; the AI pass enriches it
    when the local model is available and fast enough to answer."""
    text = (text or "").strip()
    if not text:
        return {"profile": {}}, False, None

    data = _parse_heuristic(text)

    err = ollama_client.preflight()
    if err:
        return data, False, err

    sections = _split_sections(text)
    used_ai = False
    errors: list[str] = []

    prof, err = _ai_profile(sections, text)
    if prof:
        _merge_profile(data["profile"], prof)
        used_ai = True
    elif err:
        errors.append("details: " + err)

    exps, err = _ai_experiences(sections, text)
    if exps:
        data["experiences"] = exps
        used_ai = True
    elif err:
        errors.append("experience: " + err)

    extras, err = _ai_extras(sections, text)
    if extras:
        for key in ("education", "certifications", "skills", "languages"):
            if extras.get(key):
                data[key] = extras[key]
        used_ai = True
    elif err:
        errors.append("skills and education: " + err)

    return data, used_ai, ("; ".join(errors) if errors else None)


def _merge_profile(base: dict, incoming: dict) -> None:
    """Model output fills a few safe profile fields, nothing else.

    A local model once wrote a LinkedIn URL into work_authorization and
    invented salary expectations from revenue figures, so anything outside the
    whitelist is ignored no matter what the model returns.
    """
    for key, value in incoming.items():
        if key not in _AI_PROFILE_FIELDS or key in _EXACT_FIELDS:
            continue
        if isinstance(value, (list, tuple)):
            value = " ".join(str(v).strip() for v in value)
        value = str(value).strip() if value is not None else ""
        if value:
            base[key] = value


# --- the three AI calls ----------------------------------------------------

_RULES = (
    "Use ONLY facts present in the text. Never invent employers, dates, "
    "metrics, titles, or skills. If a field is not present, use an empty "
    "string. Output JSON only."
)


def _ai_profile(sections: dict[str, str], text: str) -> tuple[dict | None, str | None]:
    """Header plus summary only -- a small prompt and a small answer."""
    parts = [p for p in (sections.get("header"), sections.get("summary")) if p]
    snippet = "\n\n".join(parts) or text[:2000]
    data, err = ollama_client.generate_json(
        "Resume section:\n\n" + snippet[:4000] + "\n\n"
        "Return JSON with keys: name, title, location, summary. The title is "
        "the person's current job title. The summary is at most 3 sentences "
        "drawn from the text.",
        system="You extract resume header details into JSON. " + _RULES,
        timeout=120,
    )
    if err:
        return None, err
    return (data if isinstance(data, dict) else None), None


def _ai_experiences(sections: dict[str, str], text: str) -> tuple[list | None, str | None]:
    """The expensive call -- scoped to the experience section so the model does
    not re-read the whole resume."""
    snippet = _section(sections, "experience", fallback=text)
    data, err = ollama_client.generate_json(
        "Work experience section:\n\n" + snippet[:8000] + "\n\n"
        "Return a JSON object with one key, experiences, holding a list of "
        "objects with the keys company, role, location, dates, and bullets. "
        "bullets is a list of strings. Copy each bullet across verbatim and "
        "keep every number exactly as written.",
        system="You extract work experience into JSON. " + _RULES,
        timeout=420,
    )
    if err:
        return None, err
    items = data.get("experiences") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return None, "the local model did not return a list of experiences"
    return [_norm_experience(e) for e in items if isinstance(e, dict)], None


def _norm_experience(exp: dict) -> dict:
    """Accept bullets as plain strings or as {text, skill_tags} objects."""
    bullets = []
    for blt in exp.get("bullets") or []:
        if isinstance(blt, str):
            bullets.append({"text": blt.strip(), "skill_tags": []})
        elif isinstance(blt, dict):
            tags = blt.get("skill_tags") or []
            bullets.append({
                "text": str(blt.get("text", "")).strip(),
                "skill_tags": [str(t).strip() for t in tags if str(t).strip()],
            })
    return {
        "company": str(exp.get("company", "")).strip(),
        "role": str(exp.get("role", "")).strip(),
        "location": str(exp.get("location", "")).strip(),
        "dates": str(exp.get("dates", "")).strip(),
        "context": str(exp.get("context", "")).strip(),
        "bullets": [b for b in bullets if b["text"]],
    }


def _ai_extras(sections: dict[str, str], text: str) -> tuple[dict | None, str | None]:
    """Education, certifications, skills and languages in one short call."""
    parts = [
        sections.get("education"), sections.get("certifications"),
        sections.get("skills"), sections.get("languages"),
    ]
    snippet = "\n\n".join(p for p in parts if p) or text[-4000:]
    data, err = ollama_client.generate_json(
        "Resume sections:\n\n" + snippet[:6000] + "\n\n"
        "Return a JSON object with these keys: education (list of objects with "
        "degree, school, location, dates), certifications (list of objects with "
        "name, issuer, date), skills (list of objects with name, category, "
        "proficiency), languages (list of objects with name, proficiency). "
        "Skill names are short, at most 4 words.",
        system="You extract resume qualifications into JSON. " + _RULES,
        timeout=240,
    )
    if err:
        return None, err
    if not isinstance(data, dict):
        return None, "the local model did not return an object"
    return {k: v for k, v in data.items() if isinstance(v, list)}, None


# --- deterministic fallback ------------------------------------------------

_SKILL_SPLIT_RE = re.compile(r"[,;•|]")
_DATE_RE = re.compile(r"(?:19|20)\d{2}|present|current", re.I)
_DATE_ONLY_RE = re.compile(
    r"^(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2}\s*(?:[–-]\s*(?:present|current|(?:19|20)\d{2}))?$",
    re.I,
)


def _split_skill_items(line: str) -> list[str]:
    """Break one skills-section line into candidate skill names."""
    parts: list[str] = []
    for chunk in _SKILL_SPLIT_RE.split(line):
        chunk = chunk.strip().strip("•-–*").strip()
        if chunk:
            parts.append(chunk)
    return parts


def _is_skill_name(name: str) -> bool:
    """A skill is short and looks like a phrase, not a sentence or a URL."""
    if not (1 <= len(name.split()) <= 5):
        return False
    if not (2 <= len(name) <= 60):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 +#&/.()'’-]*", name))


def _heuristic_skills(text: str) -> list[dict]:
    """Skills from a skills/competencies section, tolerating 'Category: items'."""
    if not text:
        return []
    skills: list[dict] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        category = ""
        head, sep, rest = line.partition(":")
        if sep and head.strip() and len(head.strip()) <= 40 and rest.strip():
            category = head.strip()
            line = rest.strip()
        for item in _split_skill_items(line):
            name = item.strip().strip("()").strip()
            key = name.lower()
            if _is_skill_name(name) and key not in seen:
                seen.add(key)
                skills.append({"name": name, "category": category, "proficiency": ""})
    return skills


def _heuristic_experiences(text: str) -> list[dict]:
    """Work history from 'Role | Company' blocks, with bullets.

    Deliberately plain: this is the no-AI floor. The local model enriches it
    when available, and the user reviews the result before it is applied.
    """
    if not text:
        return []
    experiences: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if ln.startswith(("•", "-", "*", "–")) or re.match(r"^\d{1,2}[.)]\s", ln):
            if current is not None:
                current["bullets"].append(
                    {"text": re.sub(r"^[•\-–*\d.)\s]+", "", ln).strip(), "skill_tags": []}
                )
            continue
        if "|" in ln:
            left, right = (p.strip() for p in ln.split("|", 1))
            if _DATE_RE.search(right) and not _DATE_RE.search(left):
                if current is not None:
                    current["location"] = current["location"] or left
                    current["dates"] = current["dates"] or right
                continue
            current = {"company": right, "role": left, "location": "",
                       "dates": "", "context": "", "bullets": []}
            experiences.append(current)
            continue
        if _DATE_ONLY_RE.fullmatch(ln):
            if current is not None and not current["dates"]:
                current["dates"] = ln
            continue
        if current is not None:
            current["context"] = (current["context"] + " " + ln).strip()
    return experiences


def _heuristic_education(text: str) -> list[dict]:
    """Each non-empty education line becomes one entry. Education only feeds
    text similarity, so a light touch is enough."""
    if not text:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip().strip("•-–*").strip()
        if line and len(line) >= 3:
            out.append({"degree": line, "school": "", "location": "", "dates": ""})
    return out


def _heuristic_title(text: str, sections: dict[str, str]) -> str:
    """Best-effort title from the header: the first short, non-contact line
    after the name. Empty when nothing looks safe."""
    header = sections.get("header") or text[:1200]
    for ln in (l.strip() for l in header.splitlines() if l.strip()):
        if EMAIL_RE.search(ln) or URL_RE.search(ln) or PHONE_RE.search(ln) or "|" in ln:
            continue
        words = [w for w in ln.split() if any(c.isalnum() for c in w)]
        if 2 <= len(words) <= 10 and not ln.isupper() and not any(c.isdigit() for c in ln):
            return ln
    return ""


def _auth_statement(text: str) -> str:
    """An explicit work-authorisation claim, or empty when none is made."""
    m = _AUTH_RE.search(text)
    return m.group(0).strip() if m else ""


def _parse_heuristic(text: str) -> dict:
    sections = _split_sections(text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    linkedin = LINKEDIN_RE.search(text)
    # portfolio: first link that is not linkedin/email. Tolerates a bare
    # domain ("syedmaazsaif.com") with no scheme.
    portfolio = ""
    for m in _PORTFOLIO_RE.finditer(text):
        cand = m.group(0).strip()
        if "linkedin.com" in cand.lower():
            continue
        portfolio = cand if "://" in cand else "https://" + cand
        break
    # name: first line that looks like a name (letters and spaces, 2-4 words)
    name = ""
    for ln in lines[:6]:
        if EMAIL_RE.search(ln) or URL_RE.search(ln):
            continue
        words = ln.split()
        if 1 < len(words) <= 4 and all(w[0].isalpha() for w in words if w):
            name = ln
            break
    summary = (sections.get("summary") or " ".join(lines[:20]))[:900]
    return {
        "profile": {
            "name": name,
            "title": _heuristic_title(text, sections),
            "email": email.group(0) if email else "",
            "phone": phone.group(0).strip() if phone else "",
            "linkedin": linkedin.group(0) if linkedin else "",
            "portfolio": portfolio,
            "work_authorization": _auth_statement(text),
            "summary": summary,
        },
        "experiences": _heuristic_experiences(sections.get("experience", "")),
        "education": _heuristic_education(sections.get("education", "")),
        "certifications": [],
        "skills": _heuristic_skills(sections.get("skills", "")),
        "languages": [],
    }
