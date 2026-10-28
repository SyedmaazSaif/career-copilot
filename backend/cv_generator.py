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
        "contact": _contact_line1(profile),
        "contact2": _contact_line2(profile),
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


def _contact_line1(profile) -> str:
    """Header line 1 in the master format: location | phone | email."""
    if not profile:
        return ""
    parts = [profile.location, profile.phone, profile.email]
    return "  |  ".join(p for p in parts if p)


def _contact_line2(profile) -> str:
    """Header line 2 in the master format: website | linkedin."""
    if not profile:
        return ""
    parts = [profile.portfolio, profile.linkedin]
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


def _title_slug(text: str, fallback: str = "CV") -> str:
    """'Syed maaz saif' -> 'Syed_Maaz_Saif'; Title Case, words joined with _."""
    s = re.sub(r"[^A-Za-z0-9]+", " ", (text or "").strip()).title()
    return "_".join(s.split()) or fallback


def _esc(text: str) -> str:
    """Escape text for reportlab Paragraph XML."""
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_docx(cv_data: dict, path: Path) -> None:
    """Write the master-format CV as a clean, single-column, ATS-safe docx."""
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

    def centered(text, size=9, bold=False):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        r.font.size = Pt(size)
        r.bold = bold
        return p

    # Header: name (caps), title, two contact lines — the master format.
    centered((cv_data["name"] or "").upper(), size=17, bold=True)
    if cv_data["title"]:
        centered(cv_data["title"], size=11)
    if cv_data["contact"]:
        centered(cv_data["contact"], size=9)
    if cv_data["contact2"]:
        centered(cv_data["contact2"], size=9)

    if cv_data["summary"]:
        heading("Professional Summary")
        doc.add_paragraph(cv_data["summary"])

    if cv_data["skills_by_cat"]:
        heading("Core Competencies")
        for cat, names in cv_data["skills_by_cat"]:
            p = doc.add_paragraph()
            p.add_run(f"{cat}: ").bold = True
            p.add_run(", ".join(names))

    if cv_data["experiences"]:
        heading("Professional Experience")
        for exp in cv_data["experiences"]:
            p = doc.add_paragraph()
            r = p.add_run(f"{exp['role']}")
            r.bold = True
            if exp.get("company"):
                p.add_run(f"   |   {exp['company']}")
            meta = "  |  ".join(x for x in [exp.get("location"), exp.get("dates")] if x)
            if meta:
                mp = doc.add_paragraph()
                mp.add_run(meta).font.size = Pt(9)
            for b in exp["bullets"]:
                doc.add_paragraph(b, style="List Bullet")

    edu = cv_data["education"] or []
    certs = cv_data["certifications"] or []
    if edu or certs:
        heading("Education & Certifications")
        for e in edu:
            p = doc.add_paragraph()
            p.add_run(e["degree"]).bold = True
            meta = "  |  ".join(x for x in [e["school"], e["location"], e["dates"]] if x)
            if meta:
                p.add_run(f"   {meta}").font.size = Pt(9)
        for c in certs:
            meta = "  |  ".join(x for x in [c["name"], c["issuer"], c["date"]] if x)
            doc.add_paragraph(meta)

    if cv_data["languages"]:
        heading("Languages")
        doc.add_paragraph(", ".join(cv_data["languages"]))

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


def _output_dir(profile) -> Path:
    """Where generated files go: the user's chosen folder, or the app default."""
    chosen = getattr(profile, "cv_folder", "") if profile else ""
    chosen = (chosen or "").strip()
    if chosen:
        return Path(chosen).expanduser()
    return CV_DIR


def build_pdf(cv_data: dict, path: Path) -> None:
    """Write the master-format CV as a clean, text-based (ATS-safe) PDF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    dark = colors.HexColor("#1B2733")
    grey = colors.HexColor("#555555")

    name_st = ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=17, alignment=1, spaceAfter=2)
    title_st = ParagraphStyle("title", fontName="Helvetica", fontSize=11, alignment=1, spaceAfter=2)
    contact_st = ParagraphStyle("contact", fontName="Helvetica", fontSize=9, alignment=1, textColor=dark, spaceAfter=1)
    heading_st = ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=10.5, textColor=dark, spaceBefore=10, spaceAfter=3)
    body_st = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=12.5, spaceAfter=4)
    bullet_st = ParagraphStyle("bullet", fontName="Helvetica", fontSize=9.5, leading=12.5, leftIndent=14, spaceAfter=2)
    meta_st = ParagraphStyle("meta", fontName="Helvetica", fontSize=8.5, textColor=grey, spaceAfter=2)

    doc = SimpleDocTemplate(
        str(path), pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title=cv_data.get("name") or "CV",
    )
    story = []

    story.append(Paragraph(_esc(cv_data.get("name") or "").upper(), name_st))
    if cv_data.get("title"):
        story.append(Paragraph(_esc(cv_data["title"]), title_st))
    if cv_data.get("contact"):
        story.append(Paragraph(_esc(cv_data["contact"]), contact_st))
    if cv_data.get("contact2"):
        story.append(Paragraph(_esc(cv_data["contact2"]), contact_st))

    def heading(text):
        story.append(Paragraph(text, heading_st))

    if cv_data.get("summary"):
        heading("PROFESSIONAL SUMMARY")
        story.append(Paragraph(_esc(cv_data["summary"]), body_st))

    if cv_data.get("skills_by_cat"):
        heading("CORE COMPETENCIES")
        for cat, names in cv_data["skills_by_cat"]:
            story.append(Paragraph(f"<b>{_esc(cat)}:</b> {_esc(', '.join(names))}", body_st))

    if cv_data.get("experiences"):
        heading("PROFESSIONAL EXPERIENCE")
        for exp in cv_data["experiences"]:
            story.append(Paragraph(f"<b>{_esc(exp['role'])}</b>  |  {_esc(exp.get('company', ''))}", body_st))
            meta = "  |  ".join(x for x in [exp.get("location"), exp.get("dates")] if x)
            if meta:
                story.append(Paragraph(_esc(meta), meta_st))
            for b in exp["bullets"]:
                story.append(Paragraph(f"-  {_esc(b)}", bullet_st))

    edu = cv_data.get("education") or []
    certs = cv_data.get("certifications") or []
    if edu or certs:
        heading("EDUCATION &amp; CERTIFICATIONS")
        for e in edu:
            meta = "  |  ".join(x for x in [e.get("school"), e.get("location"), e.get("dates")] if x)
            story.append(Paragraph(f"<b>{_esc(e.get('degree', ''))}</b>  {_esc(meta)}", body_st))
        for c in certs:
            meta = "  |  ".join(x for x in [c.get("name"), c.get("issuer"), c.get("date")] if x)
            story.append(Paragraph(_esc(meta), body_st))

    if cv_data.get("languages"):
        heading("LANGUAGES")
        story.append(Paragraph(_esc(", ".join(cv_data["languages"])), body_st))

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)


def generate_cv(db: Session, job, answers: dict) -> dict:
    """Full pipeline: gather -> select+reword -> PDF + docx -> verify."""
    use_ai = ollama_client.preflight() is None
    data = gather_profile(db)
    cv_data = build_cv_data(data, job, answers, use_ai)
    flags = verify_cv(cv_data, data)

    stem = f"{_title_slug(cv_data['name'])}_{_title_slug(cv_data['title'], fallback='Role')}"
    out_dir = _output_dir(data["profile"])
    pdf_path = out_dir / f"{stem}.pdf"
    docx_path = out_dir / f"{stem}.docx"

    build_pdf(cv_data, pdf_path)
    build_docx(cv_data, docx_path)

    return {
        "file_path": str(pdf_path),
        "filename": f"{stem}.pdf",
        "docx_path": str(docx_path),
        "target_title": cv_data["title"],
        "used_ai": use_ai,
        "flags": flags,
    }
