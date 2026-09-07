"""Read a resume file and turn it into profile data.

Text extraction is deterministic (pypdf / python-docx). Turning that text into
structured profile records uses the optional local Ollama model when available;
without it, a light heuristic fills contact details and the summary and leaves
the rest for the user to complete. No paid API is ever used.

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

# Contact fields the regex pass owns outright; the model never overrides these.
_EXACT_FIELDS = ("email", "phone", "linkedin", "portfolio")


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
    """Model output fills in the profile, except the fields the regex nailed."""
    for key, value in incoming.items():
        if key in _EXACT_FIELDS and base.get(key):
            continue
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
        "Return JSON with keys: name, title, location, summary, "
        "work_authorization, notice_period. The title is the person's current "
        "job title. The summary is at most 3 sentences drawn from the text.",
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

def _parse_heuristic(text: str) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    linkedin = LINKEDIN_RE.search(text)
    # portfolio: first url that is not linkedin/email
    portfolio = ""
    for m in URL_RE.finditer(text):
        if "linkedin.com" not in m.group(0).lower():
            portfolio = m.group(0)
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
    summary = " ".join(lines[:20])[:900]
    return {
        "profile": {
            "name": name,
            "email": email.group(0) if email else "",
            "phone": phone.group(0).strip() if phone else "",
            "linkedin": linkedin.group(0) if linkedin else "",
            "portfolio": portfolio,
            "summary": summary,
        },
        "experiences": [],
        "education": [],
        "certifications": [],
        "skills": [],
        "languages": [],
    }
