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


if __name__ == "__main__":
    unittest.main()
