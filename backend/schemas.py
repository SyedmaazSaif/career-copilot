"""Pydantic schemas for the Profile CMS API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Profile (singleton) ----
class ProfileBase(BaseModel):
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    portfolio: str = ""
    summary: str = ""
    work_authorization: str = ""
    notice_period: str = ""
    salary_expectation_usd: str = ""
    salary_expectation_pkr: str = ""


class ProfileOut(ProfileBase, ORMModel):
    id: int


# ---- Bullet ----
class BulletBase(BaseModel):
    text: str = ""
    skill_tags: list[str] = []
    sort_order: int = 0


class BulletCreate(BulletBase):
    pass


class BulletOut(BulletBase, ORMModel):
    id: int
    experience_id: int


# ---- Experience ----
class ExperienceBase(BaseModel):
    company: str = ""
    role: str = ""
    location: str = ""
    dates: str = ""
    context: str = ""
    sort_order: int = 0


class ExperienceCreate(ExperienceBase):
    pass


class ExperienceOut(ExperienceBase, ORMModel):
    id: int
    bullets: list[BulletOut] = []


# ---- Education ----
class EducationBase(BaseModel):
    degree: str = ""
    school: str = ""
    location: str = ""
    dates: str = ""
    sort_order: int = 0


class EducationCreate(EducationBase):
    pass


class EducationOut(EducationBase, ORMModel):
    id: int


# ---- Certification ----
class CertificationBase(BaseModel):
    name: str = ""
    issuer: str = ""
    date: str = ""
    sort_order: int = 0


class CertificationCreate(CertificationBase):
    pass


class CertificationOut(CertificationBase, ORMModel):
    id: int


# ---- Skill ----
class SkillBase(BaseModel):
    name: str = ""
    category: str = ""
    proficiency: str = ""
    sort_order: int = 0


class SkillCreate(SkillBase):
    pass


class SkillOut(SkillBase, ORMModel):
    id: int


# ---- Language ----
class LanguageBase(BaseModel):
    name: str = ""
    proficiency: str = ""
    sort_order: int = 0


class LanguageCreate(LanguageBase):
    pass


class LanguageOut(LanguageBase, ORMModel):
    id: int


# ---- Jobs ----
class JobOut(ORMModel):
    id: int
    source: str
    title: str
    company: str
    location: str
    url: str
    description: str
    requirements: list[str]
    posted: str
    tags: list[str]
    work_type: str
    employment_type: str
    score: int
    score_reason: dict
    red_flags: list[str]
    salary_min: int | None = None
    salary_max: int | None = None
    salary_text: str = ""
    stage: str
    sort_order: int
    notes: str
    first_scanned_at: datetime | None = None
    last_seen_at: datetime | None = None
    applied_at: datetime | None = None
    first_reply_at: datetime | None = None


class JobPatch(BaseModel):
    stage: str | None = None
    sort_order: int | None = None
    notes: str | None = None


class ScrapeRunOut(ORMModel):
    id: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: str
    trigger: str
    total_found: int
    total_new: int
    source_counts: dict
    error: str


class ScanStatus(BaseModel):
    running: bool
    run: ScrapeRunOut | None = None


# ---- Search settings ----
class SearchConfigIn(BaseModel):
    queries: list[str] = []
    enabled_sources: list[str] = []
    preferred_arrangements: list[str] = ["remote", "hybrid", "onsite"]
    locations: list[str] = []


class SearchConfigOut(BaseModel):
    queries: list[str]
    enabled_sources: list[str]
    all_sources: list[str]
    preferred_arrangements: list[str]
    locations: list[str] = []


# ---- Custom sources ----
class CustomSourceIn(BaseModel):
    kind: str = "rss"  # rss | greenhouse | lever | url
    value: str = ""
    label: str = ""
    enabled: bool = True


class CustomSourceOut(ORMModel):
    id: int
    kind: str
    value: str
    label: str
    enabled: bool


# ---- Add job by URL ----
class AddJobByUrl(BaseModel):
    url: str


# ---- CV generation ----
class CVGenerateRequest(BaseModel):
    answers: dict = {}


class CVPackOut(ORMModel):
    id: int
    job_id: int
    filename: str
    target_title: str
    used_ai: bool
    flags: list[str]
    created_at: datetime | None = None


# ---- Resume import ----
class ResumeParseResult(BaseModel):
    data: dict
    used_ai: bool


class ResumeApplyRequest(BaseModel):
    data: dict
    replace: bool = True


# ---- Import ----
class ImportRequest(BaseModel):
    # Optional inline YAML. If absent, the server loads the bundled
    # master_profile.yaml next to the app root.
    yaml_text: str | None = None
    replace: bool = True  # wipe existing records before importing


class ImportResult(BaseModel):
    experiences: int
    bullets: int
    education: int
    certifications: int
    skills: int
    languages: int
    profile_updated: bool
