"""Tests for the deterministic resume parser (backend/resume.py).

These lock in the no-AI floor: an upload must still produce skills, work
experience and a title when the local model is switched off or fails, so the
profile is never left empty for matching.
"""
import unittest
from unittest import mock

from backend import resume as r

SIMPLE = """JOHN DOE
Software Engineer
San Francisco, CA | john@example.com

SUMMARY
Backend engineer building web services.

SKILLS
Python, SQL, Django, AWS, Kubernetes, Docker

EXPERIENCE
Senior Software Engineer | Acme Corp
Remote | Jan 2020 – Present
Led the payments team.
• Built a billing service in Python.
• Migrated databases to PostgreSQL.

Software Engineer | Widgets Inc
New York, NY | Jun 2017 – Dec 2019
Worked on the analytics platform.

EDUCATION
BSc Computer Science | State University | 2017
"""


class SkillExtractionTests(unittest.TestCase):
    def test_skills_extracted(self):
        d = r._parse_heuristic(SIMPLE)
        names = [s["name"] for s in d["skills"]]
        for want in ("Python", "SQL", "Django", "Kubernetes", "Docker"):
            self.assertIn(want, names)

    def test_categorised_competencies(self):
        d = r._parse_heuristic(
            "SKILLS\nGrowth & Monetization: Subscription pricing, carrier billing, churn reduction"
        )
        by_name = {s["name"]: s for s in d["skills"]}
        self.assertEqual(by_name["Subscription pricing"]["category"], "Growth & Monetization")


class ExperienceExtractionTests(unittest.TestCase):
    def test_experiences_extracted(self):
        d = r._parse_heuristic(SIMPLE)
        self.assertEqual(len(d["experiences"]), 2)
        first = d["experiences"][0]
        self.assertEqual(first["company"], "Acme Corp")
        self.assertEqual(first["role"], "Senior Software Engineer")
        self.assertEqual(first["location"], "Remote")
        self.assertEqual(first["dates"], "Jan 2020 – Present")
        self.assertEqual(len(first["bullets"]), 2)

    def test_second_experience(self):
        d = r._parse_heuristic(SIMPLE)
        second = d["experiences"][1]
        self.assertEqual(second["company"], "Widgets Inc")
        self.assertEqual(second["location"], "New York, NY")


class ProfileExtractionTests(unittest.TestCase):
    def test_title_extracted(self):
        d = r._parse_heuristic(SIMPLE)
        self.assertEqual(d["profile"]["title"], "Software Engineer")

    def test_summary_uses_summary_section(self):
        d = r._parse_heuristic(SIMPLE)
        self.assertIn("backend engineer", d["profile"]["summary"].lower())

    def test_name_and_email(self):
        d = r._parse_heuristic(SIMPLE)
        self.assertEqual(d["profile"]["name"], "JOHN DOE")
        self.assertEqual(d["profile"]["email"], "john@example.com")


class ParseResumeFallbackTests(unittest.TestCase):
    def test_heuristic_data_survives_ai_being_off(self):
        with mock.patch.object(r.ollama_client, "preflight", return_value="local AI is switched off"):
            data, used_ai, err = r.parse_resume(SIMPLE)
        self.assertFalse(used_ai)
        self.assertEqual(err, "local AI is switched off")
        self.assertTrue(data["skills"])
        self.assertTrue(data["experiences"])


class ContactFieldTests(unittest.TestCase):
    def test_portfolio_bare_domain(self):
        # No https:// scheme, and next to an email + linkedin: the personal site
        # must win, not the email domain or linkedin.
        d = r._parse_heuristic(
            "JOHN DOE\nEngineer\nmyname.com | linkedin.com/in/john\njohn@example.com"
        )
        self.assertEqual(d["profile"]["portfolio"], "https://myname.com")

    def test_work_authorization_empty_when_not_stated(self):
        d = r._parse_heuristic("JOHN DOE\nEngineer\njohn@example.com")
        self.assertEqual(d["profile"]["work_authorization"], "")

    def test_work_authorization_extracted_when_stated(self):
        d = r._parse_heuristic("JOHN DOE\nAuthorized to work in the United States\n\nSKILLS\nPython")
        self.assertEqual(
            d["profile"]["work_authorization"],
            "Authorized to work in the United States",
        )


class MergeProfileGuardTests(unittest.TestCase):
    def test_only_safe_fields_are_merged(self):
        base = {}
        r._merge_profile(base, {
            "name": "Jane",
            "title": "Nurse",
            "summary": ["A", "B", "C"],  # a list must be joined, not stringified
            "work_authorization": "linkedin.com/in/x",  # regex-owned -> ignored
            "salary_expectation_usd": "USD 50000",  # invented -> ignored
            "notice_period": "N/A",  # not a resume fact -> ignored
        })
        self.assertEqual(base["name"], "Jane")
        self.assertEqual(base["title"], "Nurse")
        self.assertEqual(base["summary"], "A B C")
        self.assertNotIn("work_authorization", base)
        self.assertNotIn("salary_expectation_usd", base)
        self.assertNotIn("notice_period", base)


if __name__ == "__main__":
    unittest.main()
