"""SQLite + SQLAlchemy setup for career-copilot.

The database file is created on first run. All app data lives in one shared
SQLite file, read and written only through this backend.
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Store the db next to the backend package so it is easy to find and back up.
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "career_copilot.db"

engine = create_engine(
    f"sqlite:///{DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Columns added after the first release. On an existing database SQLite's
# create_all cannot add them, so we ALTER them in. Keeps upgrades painless with
# no migration framework. Each entry: table -> {column: "SQL type [DEFAULT ...]"}.
_COLUMN_ADDITIONS = {
    "job": {
        "work_type": "VARCHAR DEFAULT 'unknown'",
        "employment_type": "VARCHAR DEFAULT 'unknown'",
        "salary_min": "INTEGER",
        "salary_max": "INTEGER",
        "salary_text": "VARCHAR DEFAULT ''",
        "salary_parsed": "BOOLEAN DEFAULT 0",
        "company_url": "VARCHAR",
    },
    "search_config": {
        "preferred_arrangements": "JSON",
        "locations": "JSON",
        "known_sources": "JSON",
    },
}


def _ensure_columns() -> None:
    with engine.begin() as conn:
        for table, cols in _COLUMN_ADDITIONS.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if not existing:
                continue  # table will be created fresh by create_all
            for col, decl in cols.items():
                if col not in existing:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {col} {decl}"
                    )


def _backfill_descriptions() -> None:
    """Clean HTML/entities out of descriptions scanned before text cleaning
    existed. Only touches rows that still look like HTML, so it stops doing
    work after the first pass."""
    from sqlalchemy import or_

    from .models import Job
    from .textutil import clean_description

    with SessionLocal() as session:
        rows = (
            session.query(Job)
            .filter(
                or_(
                    Job.description.like("%<%"),
                    Job.description.like("%&#%"),
                    Job.description.like("%&amp;%"),
                    Job.description.like("%&nbsp;%"),
                    Job.description.like("%&quot;%"),
                    Job.description.like("%&rsquo;%"),
                    Job.description.like("%&lt;%"),
                )
            )
            .all()
        )
        changed = 0
        for job in rows:
            cleaned = clean_description(job.description or "")
            if cleaned != job.description:
                job.description = cleaned
                changed += 1
        if changed:
            session.commit()


def _backfill_salaries() -> None:
    """Parse salaries for jobs scanned before salary parsing existed. Runs once
    per row (guarded by salary_parsed), so it is cheap after the first pass."""
    from .models import Job
    from .salary import parse_salary

    with SessionLocal() as session:
        rows = session.query(Job).filter(Job.salary_parsed.is_(False)).all()
        for job in rows:
            info = parse_salary(f"{job.description or ''} {job.title or ''}")
            if info:
                job.salary_min = info["min"]
                job.salary_max = info["max"]
                job.salary_text = info["text"]
            job.salary_parsed = True
        if rows:
            session.commit()


def init_db() -> None:
    """Create tables on first run. Models register themselves on Base."""
    # Import models so their tables are registered before create_all runs.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    _backfill_descriptions()
    _backfill_salaries()

    # Ensure the singleton profile row (id=1) always exists so the UI has a
    # record to edit from the very first launch.
    from .models import Profile, SearchConfig
    from .scrapers import ALL_SOURCES, DEFAULT_QUERIES, LEGACY_SOURCES

    with SessionLocal() as session:
        if session.get(Profile, 1) is None:
            session.add(Profile(id=1))
        config = session.get(SearchConfig, 1)
        if config is None:
            # Seed with the scraper defaults so a fresh install scans sensibly.
            session.add(
                SearchConfig(
                    id=1,
                    queries=list(DEFAULT_QUERIES),
                    enabled_sources=list(ALL_SOURCES),
                    known_sources=list(ALL_SOURCES),
                )
            )
        else:
            # A board added by an app upgrade is switched on once, the first time
            # this config sees it. Boards the user switched off are already in
            # known_sources, so they stay off. A config written before this
            # column existed has been offered exactly the legacy boards.
            known = set(config.known_sources or LEGACY_SOURCES)
            fresh = [s for s in ALL_SOURCES if s not in known]
            if fresh or not config.known_sources:
                enabled = list(config.enabled_sources or [])
                config.enabled_sources = enabled + [
                    s for s in fresh if s not in enabled
                ]
                config.known_sources = sorted(known | set(ALL_SOURCES))
        session.commit()


def get_db():
    """FastAPI dependency: yield a session and always close it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
