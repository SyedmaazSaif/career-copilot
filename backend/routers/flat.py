"""Education, certifications, skills, and languages — flat CRUD via the factory."""
from ..crud_router import make_crud_router
from ..models import Certification, Education, Language, Skill
from ..schemas import (
    CertificationCreate,
    CertificationOut,
    EducationCreate,
    EducationOut,
    LanguageCreate,
    LanguageOut,
    SkillCreate,
    SkillOut,
)

education_router = make_crud_router(
    prefix="/api/education",
    tag="education",
    model=Education,
    create_schema=EducationCreate,
    out_schema=EducationOut,
)

certification_router = make_crud_router(
    prefix="/api/certifications",
    tag="certifications",
    model=Certification,
    create_schema=CertificationCreate,
    out_schema=CertificationOut,
)

skill_router = make_crud_router(
    prefix="/api/skills",
    tag="skills",
    model=Skill,
    create_schema=SkillCreate,
    out_schema=SkillOut,
)

language_router = make_crud_router(
    prefix="/api/languages",
    tag="languages",
    model=Language,
    create_schema=LanguageCreate,
    out_schema=LanguageOut,
)
