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
    },
    "search_config": {
        "preferred_arrangements": "JSON",
        "locations": "JSON",
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
    _backfill_salaries()

    # Ensure the singleton profile row (id=1) always exists so the UI has a
    # record to edit from the very first launch.
    from .models import Profile, SearchConfig

    with SessionLocal() as session:
        if session.get(Profile, 1) is None:
            session.add(Profile(id=1))
        if session.get(SearchConfig, 1) is None:
            # Seed with the scraper defaults so a fresh install scans sensibly.
            from .scrapers import ALL_SOURCES, DEFAULT_QUERIES

            session.add(
                SearchConfig(
                    id=1,
                    queries=list(DEFAULT_QUERIES),
                    enabled_sources=list(ALL_SOURCES),
                )
            )
        session.commit()


def get_db():
    """FastAPI dependency: yield a session and always close it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
