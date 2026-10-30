"""Tests for dedup (prefer direct company link) and the auto-growing registry."""
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.company_registry import (
    add_company,
    auto_add_from_jobs,
    drop_after_failures,
    record_result,
)
from backend.db import Base
from backend.ingest import ingest_jobs
from backend.models import Company, Job, Profile, SearchConfig

_PROFILE = {
    "skills": [],
    "skill_weights": {},
    "resume_text": "",
    "resume_tokens": [],
    "target_titles": [],
    "user_band": None,
    "preferred_arrangements": ["remote", "hybrid", "onsite"],
    "home_locations": [],
    "home_regions": set(),
    "years_experience": None,
    "has_resume": False,
}


class _DbTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add(Profile(id=1))
            db.add(SearchConfig(id=1))
            db.commit()


class DedupPreferenceTests(_DbTestCase):
    def test_prefers_direct_company_link(self):
        with self.Session() as db:
            ingest_jobs(db, [{
                "source": "remoteok",
                "title": "Product Manager",
                "company": "Stripe",
                "location": "Remote",
                "url": "https://remoteok.com/jobs/123",
                "description": "A great PM role.",
                "posted": "",
                "tags": [],
            }], _PROFILE)
            ingest_jobs(db, [{
                "source": "greenhouse:stripe",
                "title": "Product Manager",
                "company": "Stripe",
                "location": "Remote",
                "url": "https://boards.greenhouse.io/stripe/jobs/999",
                "description": "A great PM role.",
                "posted": "",
                "tags": [],
            }], _PROFILE)
            job = db.scalars(select(Job)).first()
            self.assertIn("greenhouse.io", job.url)
            self.assertEqual(job.source, "greenhouse:stripe")
            # only one row — the two are the same job
            self.assertEqual(len(db.scalars(select(Job)).all()), 1)


class RegistryTests(_DbTestCase):
    def test_auto_add_dedupes_boards(self):
        with self.Session() as db:
            added = auto_add_from_jobs(db, [
                {"url": "https://boards.greenhouse.io/stripe/jobs/1", "company": "Stripe"},
                {"url": "https://boards.greenhouse.io/stripe/jobs/2", "company": "Stripe"},
                {"url": "https://jobs.lever.co/netflix/abc", "company": "Netflix"},
                {"url": "https://indeed.com/job/xyz", "company": "Not Ats"},
            ])
            self.assertEqual(added, 2)
            self.assertEqual(len(db.scalars(select(Company)).all()), 2)

    def test_drop_after_three_failures(self):
        with self.Session() as db:
            add_company(db, "Stripe", "greenhouse", "stripe")
            c = db.scalars(select(Company)).first()
            for _ in range(3):
                record_result(db, c, False)
            self.assertEqual(drop_after_failures(db), 1)
            self.assertFalse(c.enabled)


if __name__ == "__main__":
    unittest.main()
