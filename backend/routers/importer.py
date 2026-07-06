"""Importer: populate Profile CMS records from master_profile.yaml.

Reads inline YAML if provided, otherwise the bundled master_profile.yaml at the
app root. By default it replaces existing records so re-importing an edited yaml
gives a clean, predictable result.
"""
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Bullet,
    Certification,
    Education,
    Experience,
    Language,
    Profile,
    Skill,
)
from ..schemas import ImportRequest, ImportResult

router = APIRouter(prefix="/api/import", tags=["import"])

# master_profile.yaml lives at the career-copilot root (two levels up from here).
# On a fresh clone the real file is absent (it is git-ignored), so fall back to
# the shipped example template so importing still demonstrates the flow.
_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_YAML = _ROOT / "master_profile.yaml"
EXAMPLE_YAML = _ROOT / "master_profile.example.yaml"


def _default_yaml_path() -> Path:
    return DEFAULT_YAML if DEFAULT_YAML.exists() else EXAMPLE_YAML

# Only these Profile columns may be set from an import.
_PROFILE_FIELDS = {
    "name", "title", "email", "phone", "location", "linkedin", "portfolio",
    "summary", "work_authorization", "notice_period",
    "salary_expectation_usd", "salary_expectation_pkr",
}


def apply_profile_data(db: Session, data: dict, replace: bool = True) -> ImportResult:
    """Populate the Profile CMS from a data dict shaped like master_profile.yaml.
    Shared by the YAML importer and the resume importer."""
    if replace:
        for model in (Bullet, Experience, Education, Certification, Skill, Language):
            db.execute(delete(model))

    counts = {
        "experiences": 0, "bullets": 0, "education": 0,
        "certifications": 0, "skills": 0, "languages": 0,
    }

    # Profile (singleton)
    profile_updated = False
    prof_data = data.get("profile")
    if isinstance(prof_data, dict):
        profile = db.get(Profile, 1) or Profile(id=1)
        db.add(profile)
        for key, value in prof_data.items():
            if key in _PROFILE_FIELDS and value is not None:
                setattr(profile, key, str(value).strip())
        profile_updated = True

    # Experiences + nested bullets
    for i, exp in enumerate(data.get("experiences", []) or []):
        experience = Experience(
            company=str(exp.get("company", "")).strip(),
            role=str(exp.get("role", "")).strip(),
            location=str(exp.get("location", "")).strip(),
            dates=str(exp.get("dates", "")).strip(),
            context=str(exp.get("context", "")).strip(),
            sort_order=i,
        )
        db.add(experience)
        db.flush()  # assign experience.id for the bullets
        counts["experiences"] += 1
        for j, blt in enumerate(exp.get("bullets", []) or []):
            tags = blt.get("skill_tags", []) or []
            db.add(Bullet(
                experience_id=experience.id,
                text=str(blt.get("text", "")).strip(),
                skill_tags=[str(t).strip() for t in tags],
                sort_order=j,
            ))
            counts["bullets"] += 1

    for i, ed in enumerate(data.get("education", []) or []):
        db.add(Education(
            degree=str(ed.get("degree", "")).strip(),
            school=str(ed.get("school", "")).strip(),
            location=str(ed.get("location", "")).strip(),
            dates=str(ed.get("dates", "")).strip(),
            sort_order=i,
        ))
        counts["education"] += 1

    for i, ct in enumerate(data.get("certifications", []) or []):
        db.add(Certification(
            name=str(ct.get("name", "")).strip(),
            issuer=str(ct.get("issuer", "")).strip(),
            date=str(ct.get("date", "")).strip(),
            sort_order=i,
        ))
        counts["certifications"] += 1

    for i, sk in enumerate(data.get("skills", []) or []):
        db.add(Skill(
            name=str(sk.get("name", "")).strip(),
            category=str(sk.get("category", "")).strip(),
            proficiency=str(sk.get("proficiency", "")).strip(),
            sort_order=i,
        ))
        counts["skills"] += 1

    for i, lg in enumerate(data.get("languages", []) or []):
        db.add(Language(
            name=str(lg.get("name", "")).strip(),
            proficiency=str(lg.get("proficiency", "")).strip(),
            sort_order=i,
        ))
        counts["languages"] += 1

    db.commit()
    return ImportResult(profile_updated=profile_updated, **counts)


@router.post("/yaml", response_model=ImportResult)
def import_yaml(payload: ImportRequest, db: Session = Depends(get_db)):
    if payload.yaml_text:
        raw = payload.yaml_text
    else:
        path = _default_yaml_path()
        if not path.exists():
            raise HTTPException(
                404, "no yaml supplied and no master_profile.yaml/.example.yaml found"
            )
        raw = path.read_text(encoding="utf-8")

    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise HTTPException(400, f"could not parse yaml: {exc}")

    if not isinstance(data, dict):
        raise HTTPException(400, "yaml root must be a mapping")

    return apply_profile_data(db, data, replace=payload.replace)
