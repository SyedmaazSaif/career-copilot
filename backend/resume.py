"""Read a resume file and turn it into profile data.

Text extraction is deterministic (pypdf / python-docx). Turning that text into
structured profile records uses the optional local Ollama model when available;
without it, a light heuristic fills contact details and the summary and leaves
the rest for the user to complete. No paid API is ever used.
"""
from __future__ import annotations

import io
import re

from . import ollama_client

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+", re.I)
URL_RE = re.compile(r"https?://[\w.-]+\.[a-z]{2,}(?:/\S*)?", re.I)


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


_SCHEMA_HINT = (
    "profile{name,title,email,phone,location,linkedin,portfolio,summary,"
    "work_authorization,notice_period,salary_expectation_usd,salary_expectation_pkr}, "
    "experiences[{company,role,location,dates,context,"
    "bullets[{text,skill_tags[]}]}], education[{degree,school,location,dates}], "
    "certifications[{name,issuer,date}], skills[{name,category,proficiency}], "
    "languages[{name,proficiency}]"
)


def parse_resume(text: str) -> tuple[dict, bool]:
    """Return (profile_data, used_ai). profile_data is shaped like
    master_profile.yaml. Falls back to a heuristic when Ollama is unavailable."""
    text = (text or "").strip()
    if not text:
        return {"profile": {}}, False

    ai = _parse_with_ollama(text)
    if ai is not None:
        return ai, True
    return _parse_heuristic(text), False


def _parse_with_ollama(text: str) -> dict | None:
    system = (
        "You extract a resume into structured JSON. Use ONLY facts present in the "
        "resume text. Never invent employers, dates, metrics, or skills. If a field "
        "is not present, leave it empty. Output JSON only."
    )
    prompt = (
        f"Resume text:\n\n{text[:12000]}\n\n"
        f"Return a JSON object with exactly these keys: {_SCHEMA_HINT}. "
        "skill_tags and skills should be short skill names. Output JSON only."
    )
    data = ollama_client.generate_json(prompt, system=system)
    if isinstance(data, dict) and ("profile" in data or "experiences" in data):
        return data
    return None


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
