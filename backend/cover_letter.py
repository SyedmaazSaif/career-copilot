"""Cover letter and screener answers, built from Profile facts only.

Same no-invention rule as the CV (see cv_boundary.py): every sentence is drawn
from the profile. The templates are deterministic — no AI is required and no
fact is ever invented.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from .cv_generator import (
    _contact_line1,
    _contact_line2,
    _esc,
    _output_dir,
    _title_slug,
    gather_profile,
    select_content,
)


def screener_answers(db: Session) -> list[dict]:
    """Ready-made answers for common application questions, from the profile."""
    data = gather_profile(db)
    profile = data["profile"]
    rows: list[dict] = []
    if not profile:
        return rows

    if profile.notice_period:
        rows.append({"question": "What is your notice period?", "answer": profile.notice_period})
    salary = " / ".join(
        x for x in [profile.salary_expectation_usd, profile.salary_expectation_pkr] if x
    )
    if salary:
        rows.append({"question": "What is your expected salary?", "answer": salary})
    if profile.work_authorization:
        rows.append(
            {
                "question": "Do you have the right to work in this location?",
                "answer": profile.work_authorization,
            }
        )
    if profile.location:
        rows.append({"question": "Where are you based?", "answer": profile.location})
    if profile.summary:
        rows.append({"question": "Tell us about yourself.", "answer": profile.summary})
    return rows


def _cover_text(data: dict, job) -> str:
    profile = data["profile"]
    selected = select_content(data, job)
    name = (profile.name or "").strip() if profile else ""
    title = (profile.title or "").strip() if profile else ""
    summary = (profile.summary or "").strip() if profile else ""
    contact1 = _contact_line1(profile)
    contact2 = _contact_line2(profile)

    paras = ["Dear Hiring Manager,"]

    intro = f"I am writing to apply for the {job.title} role at {job.company}."
    if title:
        intro += f" I bring a background as a {title}."
    if summary:
        intro += f" {summary}"
    paras.append(intro)

    for item in selected["experiences"][:2]:
        exp = item["exp"]
        bullets = [b.text for b in item["bullets"][:2]]
        head = f"At {exp.company}, as {exp.role}"
        if exp.dates:
            head += f" ({exp.dates})"
        if bullets:
            body = " ".join(bullets)
            body = body[0].lower() + body[1:]
            paras.append(f"{head}, {body}")

    if selected["skills"]:
        names = [s.name for s in selected["skills"][:8]]
        paras.append(f"Key strengths I would bring include {', '.join(names)}.")

    paras.append(
        "I would welcome the chance to discuss how my experience can help "
        + (job.company or "your team")
        + ". Thank you for your consideration."
    )
    paras.append("Sincerely,")
    paras.append(name)
    if contact1:
        paras.append(contact1)
    if contact2:
        paras.append(contact2)

    return "\n\n".join(p for p in paras if p)


def _build_cover_pdf(text: str, path: Path, title: str) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    style = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=15)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
        title=title,
    )
    story = [Paragraph(_esc(p), style) for p in text.split("\n\n")]
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)


def generate_cover_letter(db: Session, job) -> dict:
    """Return the cover letter text and save a PDF next to the CV."""
    data = gather_profile(db)
    text = _cover_text(data, job)
    name = (data["profile"].name or "").strip() if data["profile"] else ""
    stem = f"{_title_slug(name)}_Cover_Letter"
    out_dir = _output_dir(data["profile"])
    pdf_path = out_dir / f"{stem}.pdf"
    _build_cover_pdf(text, pdf_path, f"Cover Letter — {job.company or ''}")
    return {"text": text, "filename": f"{stem}.pdf", "file_path": str(pdf_path)}
