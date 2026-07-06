"""SQLAlchemy models for the Profile CMS.

The Profile CMS is the single source of truth for every CV, cover letter, and
screener answer the app produces. Nothing may be generated that is not present
in these records. See cv_boundary.py for the rule enforced at generation time.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .db import Base


def _now() -> datetime:
    return datetime.utcnow()


class Profile(Base):
    """Singleton (id=1). The person and their job-search parameters."""

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # Identity and contact
    name: Mapped[str] = mapped_column(String, default="")
    title: Mapped[str] = mapped_column(String, default="")
    email: Mapped[str] = mapped_column(String, default="")
    phone: Mapped[str] = mapped_column(String, default="")
    location: Mapped[str] = mapped_column(String, default="")
    linkedin: Mapped[str] = mapped_column(String, default="")
    portfolio: Mapped[str] = mapped_column(String, default="")
    summary: Mapped[str] = mapped_column(Text, default="")

    # Job-search parameters
    work_authorization: Mapped[str] = mapped_column(Text, default="")
    notice_period: Mapped[str] = mapped_column(String, default="")
    salary_expectation_usd: Mapped[str] = mapped_column(String, default="")
    salary_expectation_pkr: Mapped[str] = mapped_column(String, default="")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )


class Experience(Base):
    __tablename__ = "experience"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String, default="")
    location: Mapped[str] = mapped_column(String, default="")
    dates: Mapped[str] = mapped_column(String, default="")  # e.g. "Mar 2026 – Present"
    context: Mapped[str] = mapped_column(Text, default="")  # one-line role summary
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    bullets: Mapped[list[Bullet]] = relationship(
        back_populates="experience",
        cascade="all, delete-orphan",
        order_by="Bullet.sort_order",
    )


class Bullet(Base):
    """A single achievement line. Skill tags are stored as a JSON list of
    strings so a bullet can carry the skills it demonstrates."""

    __tablename__ = "bullet"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experience_id: Mapped[int] = mapped_column(
        ForeignKey("experience.id", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text, default="")
    skill_tags: Mapped[list] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    experience: Mapped[Experience] = relationship(back_populates="bullets")


class Education(Base):
    __tablename__ = "education"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    degree: Mapped[str] = mapped_column(String, default="")
    school: Mapped[str] = mapped_column(String, default="")
    location: Mapped[str] = mapped_column(String, default="")
    dates: Mapped[str] = mapped_column(String, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Certification(Base):
    __tablename__ = "certification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    issuer: Mapped[str] = mapped_column(String, default="")
    date: Mapped[str] = mapped_column(String, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Skill(Base):
    """A skill with an honest self-assessed proficiency. Category groups skills
    the way the master CV does (e.g. 'Growth & Monetization')."""

    __tablename__ = "skill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    category: Mapped[str] = mapped_column(String, default="")
    proficiency: Mapped[str] = mapped_column(String, default="")  # e.g. Expert
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Language(Base):
    __tablename__ = "language"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    proficiency: Mapped[str] = mapped_column(String, default="")  # e.g. Native
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


# ---- Jobs + CRM (Phase 2) ----
STAGES = ["Sourced", "Applied", "Screening", "Interview", "Offer", "Closed"]


class Job(Base):
    """A discovered job, scored against the Profile and tracked through the
    pipeline. dedupe_key normalises title+company so re-scans do not duplicate."""

    __tablename__ = "job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Raw scraped fields
    source: Mapped[str] = mapped_column(String, default="")
    title: Mapped[str] = mapped_column(String, default="")
    company: Mapped[str] = mapped_column(String, default="")
    location: Mapped[str] = mapped_column(String, default="")
    url: Mapped[str] = mapped_column(String, default="", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[list] = mapped_column(JSON, default=list)  # extracted lines
    posted: Mapped[str] = mapped_column(String, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)

    # Classification
    work_type: Mapped[str] = mapped_column(String, default="unknown", index=True)  # remote|hybrid|onsite|unknown
    employment_type: Mapped[str] = mapped_column(String, default="unknown", index=True)  # full-time|part-time|contract|internship|unknown

    # Scoring
    score: Mapped[int] = mapped_column(Integer, default=0)  # 0-100 fit
    score_reason: Mapped[dict] = mapped_column(JSON, default=dict)  # component breakdown
    red_flags: Mapped[list] = mapped_column(JSON, default=list)

    # Dedupe
    dedupe_key: Mapped[str] = mapped_column(String, default="", index=True)

    # CRM
    stage: Mapped[str] = mapped_column(String, default="Sourced", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")

    # Lifecycle timestamps (drive analytics)
    first_scanned_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_reply_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SearchConfig(Base):
    """Singleton (id=1). What the scanner searches for and which boards it uses.
    Editable from the Settings screen so the user controls their own search."""

    __tablename__ = "search_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    queries: Mapped[list] = mapped_column(JSON, default=list)  # search terms
    enabled_sources: Mapped[list] = mapped_column(JSON, default=list)  # board names
    # Which work arrangements the user wants; drives scoring + the default filter.
    preferred_arrangements: Mapped[list] = mapped_column(
        JSON, default=lambda: ["remote", "hybrid", "onsite"]
    )


class CustomSource(Base):
    """A user-added job source: an RSS feed, a Greenhouse/Lever company board, or
    a best-effort generic page. Scanned alongside the built-in boards."""

    __tablename__ = "custom_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String, default="rss")  # rss|greenhouse|lever|url
    value: Mapped[str] = mapped_column(String, default="")  # url or company slug
    label: Mapped[str] = mapped_column(String, default="")
    enabled: Mapped[bool] = mapped_column(default=True)


class CVPack(Base):
    """A generated CV for a specific job. The docx lives on disk; this row links
    it to the job and records the verification flags."""

    __tablename__ = "cv_pack"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String, default="")
    filename: Mapped[str] = mapped_column(String, default="")
    target_title: Mapped[str] = mapped_column(String, default="")
    used_ai: Mapped[bool] = mapped_column(default=False)
    flags: Mapped[list] = mapped_column(JSON, default=list)  # untraceable-claim warnings
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ScrapeRun(Base):
    """One scan. Logged for the run history and analytics."""

    __tablename__ = "scrape_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="running")  # running|done|error
    trigger: Mapped[str] = mapped_column(String, default="manual")  # manual|daily
    total_found: Mapped[int] = mapped_column(Integer, default=0)
    total_new: Mapped[int] = mapped_column(Integer, default=0)
    source_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
