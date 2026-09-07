"""Generate a tailored, ATS-friendly CV from Profile facts only.

Follows the no-invention rule in cv_boundary.py: the CV only selects, reorders,
and rewords content that already exists in the Profile. Rewording uses the
optional local Ollama model when available; otherwise the original wording is
kept. A verification pass flags anything in the output that cannot be traced
back to the Profile.
"""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import ollama_client
from .models import Certification, Education, Experience, Language, Profile, Skill

CV_DIR = Path(__file__).resolve().parent / "data" / "cv"


def gather_profile(db: Session) -> dict:
    profile = db.get(Profile, 1)
    exps = db.scalars(select(Experience).order_by(Experience.sort_order, Experience.id)).all()
    return {
        "profile": profile,
        "experiences": exps,
        "skills": db.scalars(select(Skill).order_by(Skill.sort_order)).all(),
        "education": db.scalars(select(Education).order_by(Education.sort_order)).all(),
        "certifications": db.scalars(select(Certification).order_by(Certification.sort_order)).all(),
        "languages": db.scalars(select(Language).order_by(Language.sort_order)).all(),
    }


def _job_keywords(job) -> set[str]:
    text = f"{job.title} {job.description}".lower()
    return set(re.findall(r"[a-z][a-z+/.-]{2,}", text))


def _bullet_relevance(bullet, keywords: set[str]) -> int:
    """How many of the bullet's own words / skill tags appear in the job."""
    words = set(re.findall(r"[a-z][a-z+/.-]{2,}", bullet.text.lower()))
    tag_hit = sum(1 for t in (bullet.skill_tags or []) if t.lower() in " ".join(keywords))
    return len(words & keywords) + 2 * tag_hit


def select_content(data: dict, job, emphasis: str = "") -> dict:
    """Choose and order the most relevant experiences/bullets/skills for the job.
    Nothing new is created — only selection and ordering."""
    keywords = _job_keywords(job)
    if emphasis:
        keywords |= set(re.findall(r"[a-z][a-z+/.-]{2,}", emphasis.lower()))

    experiences = []
    for exp in data["experiences"]:
        ranked = sorted(
            exp.bullets, key=lambda b: _bullet_relevance(b, keywords), reverse=True
        )
        experiences.append({"exp": exp, "bullets": ranked})

    # Skills ordered by whether they appear in the job.
    skills = sorted(
        data["skills"],
        key=lambda s: (s.name.lower().split()[0] if s.name else "") in keywords,
        reverse=True,
    )
    return {"experiences": experiences, "skills": skills}


def _reword(text: str, job, use_ai: bool) -> str:
    """Reword a bullet for the job's language WITHOUT changing its meaning or
    adding facts. Deterministic identity when AI is off."""
    if not use_ai:
        return text
    system = (
        "You rewrite a single resume bullet to better match a job, but you must "
        "NOT add, remove, or change any fact, metric, employer, title, date, or "
        "number. Keep every number identical. Keep it one sentence. No dashes. "
        "Return only the rewritten bullet."
    )
    prompt = f"Job title: {job.title}\n\nBullet: {text}\n\nRewritten bullet:"
    out, _err = ollama_client.generate(
        prompt, system=system, temperature=0.3, timeout=90
    )
    if not out:
        return text
    out = out.strip().strip('"').split("\n")[0]
    # Guard: if the model dropped/added a number, keep the original.
    if _numbers(out) != _numbers(text):
        return text
    return out or text


def _numbers(s: str) -> list[str]:
    return re.findall(r"\d[\d,.]*", s)


def build_cv_data(data: dict, job, answers: dict, use_ai: bool) -> dict:
    profile = data["profile"]
    emphasis = (answers.get("emphasis") or "").strip()
    target_title = (answers.get("target_title") or job.title or (profile.title if profile else "")).strip()
    max_bullets = 3 if (answers.get("length") == "concise") else 5

    selected = select_content(data, job, emphasis)

    experiences_out = []
    for item in selected["experiences"]:
        exp = item["exp"]
        bullets = [_reword(b.text, job, use_ai) for b in item["bullets"][:max_bullets]]
        experiences_out.append({
            "role": exp.role, "company": exp.company, "location": exp.location,
            "dates": exp.dates, "bullets": bullets,
        })

    return {
        "name": profile.name if profile else "",
        "title": target_title,
        "contact": _contact_line(profile),
        "summary": profile.summary if profile else "",
        "experiences": experiences_out,
        "skills": [s.name for s in selected["skills"]],
        "skills_by_cat": _skills_by_cat(selected["skills"]),
        "education": [
            {"degree": e.degree, "school": e.school, "location": e.location, "dates": e.dates}
            for e in data["education"]
        ],
        "certifications": [
            {"name": c.name, "issuer": c.issuer, "date": c.date} for c in data["certifications"]
        ],
        "languages": [f"{l.name} ({l.proficiency})" if l.proficiency else l.name for l in data["languages"]],
    }


def _contact_line(profile) -> str:
    if not profile:
        return ""
    parts = [profile.email, profile.phone, profile.location, profile.linkedin, profile.portfolio]
    return "  |  ".join(p for p in parts if p)


def _skills_by_cat(skills) -> list[tuple[str, list[str]]]:
    cats: dict[str, list[str]] = {}
    for s in skills:
        cats.setdefault(s.category or "Skills", []).append(s.name)
    return list(cats.items())


def verify_cv(cv_data: dict, data: dict) -> list[str]:
    """Flag any CV claim not traceable to the Profile. Because we only reword
    existing bullets, this mainly catches AI drift (a changed number or a bullet
    the model invented)."""
    flags: list[str] = []
    original_bullets = {}
    for exp in data["experiences"]:
        for b in exp.bullets:
            original_bullets[b.text] = set(_numbers(b.text))

    all_original_numbers = set()
    for nums in original_bullets.values():
        all_original_numbers |= nums

    for exp in cv_data["experiences"]:
        for bullet in exp["bullets"]:
            for num in _numbers(bullet):
                if num not in all_original_numbers:
                    flags.append(
                        f"Number '{num}' in a bullet is not in your profile: \"{bullet[:60]}…\""
                    )
    return flags


def _slug(text: str, n: int = 30) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s[:n] or "cv"


def build_docx(cv_data: dict, path: Path) -> None:
    """Write a clean, single-column, ATS-safe docx (no tables, no graphics)."""
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    doc = docx.Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    def heading(text):
        p = doc.add_paragraph()
        run = p.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0x1B, 0x27, 0x33)
        p.space_after = Pt(2)
        return p

    # Header: name + title + contact
    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    nr = name_p.add_run(cv_data["name"] or "")
    nr.bold = True
    nr.font.size = Pt(18)
    if cv_data["title"]:
        tp = doc.add_paragraph()
        tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        tp.add_run(cv_data["title"]).font.size = Pt(11)
    if cv_data["contact"]:
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.add_run(cv_data["contact"]).font.size = Pt(9)

    if cv_data["summary"]:
        heading("Summary")
        doc.add_paragraph(cv_data["summary"])

    if cv_data["experiences"]:
        heading("Experience")
        for exp in cv_data["experiences"]:
            p = doc.add_paragraph()
            r = p.add_run(f"{exp['role']}")
            r.bold = True
            meta = "  |  ".join(x for x in [exp["company"], exp["location"], exp["dates"]] if x)
            if meta:
                p.add_run(f"   {meta}").font.size = Pt(9)
            for b in exp["bullets"]:
                doc.add_paragraph(b, style="List Bullet")

    if cv_data["skills_by_cat"]:
        heading("Skills")
        for cat, names in cv_data["skills_by_cat"]:
            p = doc.add_paragraph()
            p.add_run(f"{cat}: ").bold = True
            p.add_run(", ".join(names))

    if cv_data["education"]:
        heading("Education")
        for e in cv_data["education"]:
            p = doc.add_paragraph()
            p.add_run(e["degree"]).bold = True
            meta = "  |  ".join(x for x in [e["school"], e["location"], e["dates"]] if x)
            if meta:
                p.add_run(f"   {meta}").font.size = Pt(9)

    if cv_data["certifications"]:
        heading("Certifications")
        for c in cv_data["certifications"]:
            meta = "  |  ".join(x for x in [c["name"], c["issuer"], c["date"]] if x)
            doc.add_paragraph(meta)

    if cv_data["languages"]:
        heading("Languages")
        doc.add_paragraph(", ".join(cv_data["languages"]))

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


def generate_cv(db: Session, job, answers: dict) -> dict:
    """Full pipeline: gather -> select+reword -> docx -> verify. Returns a dict
    with file path, filename, used_ai, and verification flags."""
    use_ai = ollama_client.preflight() is None
    data = gather_profile(db)
    cv_data = build_cv_data(data, job, answers, use_ai)
    flags = verify_cv(cv_data, data)

    filename = f"CV_{_slug(cv_data['name'])}_{_slug(job.company)}_{job.id}.docx"
    path = CV_DIR / filename
    build_docx(cv_data, path)

    return {
        "file_path": str(path),
        "filename": filename,
        "target_title": cv_data["title"],
        "used_ai": use_ai,
        "flags": flags,
    }
