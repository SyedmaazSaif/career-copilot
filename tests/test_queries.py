"""Tests for resume-derived scan queries (backend/matching.derive_queries).

These lock in the profession-agnostic scan: search terms must come from the
user's own profile, never a fixed product-manager list, so a welder's scan asks
for welding roles and a nurse's asks for nursing roles.
"""
import unittest

from backend.matching import derive_queries


def queries(titles, skills):
    return derive_queries({"target_titles": titles, "skills": skills})


class DeriveQueriesTests(unittest.TestCase):
    def test_welder(self):
        q = queries(
            ["Welder", "Fabricator"],
            ["MIG Welding", "TIG Welding", "Blueprint Reading"],
        )
        self.assertIn("welder", q)
        self.assertIn("fabricator", q)
        self.assertIn("mig welding", q)
        self.assertNotIn("product manager", q)

    def test_nurse(self):
        q = queries(
            ["Registered Nurse", "Staff Nurse"],
            ["Patient Care", "Medication Administration", "Phlebotomy"],
        )
        self.assertIn("registered nurse", q)
        self.assertIn("patient care", q)
        self.assertIn("phlebotomy", q)

    def test_accountant(self):
        q = queries(["Tax Accountant"], ["GAAP", "Tax Preparation", "QuickBooks"])
        self.assertIn("tax accountant", q)
        self.assertIn("gaap", q)

    def test_generic_skills_are_dropped(self):
        q = queries(["Project Manager"], ["Communication", "Management", "Strategy"])
        self.assertNotIn("communication", q)
        self.assertNotIn("management", q)
        self.assertNotIn("strategy", q)
        self.assertIn("project manager", q)

    def test_core_title_split(self):
        q = queries(
            ["Product Manager — Consumer Platforms, Fintech & AI Products"], []
        )
        self.assertIn("product manager", q)

    def test_cold_start_is_empty(self):
        self.assertEqual(derive_queries({"target_titles": [], "skills": []}), [])

    def test_capped(self):
        q = queries(
            ["Product Manager"],
            [f"Alpha{i} Beta{i} Gamma{i}" for i in range(40)],
        )
        self.assertGreater(len(q), 0)
        self.assertLessEqual(len(q), 15)


if __name__ == "__main__":
    unittest.main()
