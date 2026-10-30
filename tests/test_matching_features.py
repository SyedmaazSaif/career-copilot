"""Tests for title expansion and location-eligibility rules."""
import unittest

from backend.matching import _eligibility_component
from backend.title_expansions import expand_titles


def eligibility(label_only, text, location, homes, regions):
    score, label, _flags = _eligibility_component(text, location, homes, regions)
    return label if label_only else (label, score)


class TitleExpansionTests(unittest.TestCase):
    def test_pm_expands_to_related(self):
        titles = [t.lower() for t in expand_titles(["Product Manager"])]
        self.assertIn("product owner", titles)
        self.assertIn("technical product manager", titles)
        self.assertIn("senior product manager", titles)

    def test_ba_expands_to_analyst_roles(self):
        titles = [t.lower() for t in expand_titles(["Business Analyst"])]
        self.assertIn("business systems analyst", titles)
        self.assertIn("product analyst", titles)

    def test_unknown_title_unchanged(self):
        self.assertEqual(expand_titles(["Welder"]), ["Welder"])


class EligibilityTests(unittest.TestCase):
    def test_us_only_rejects_pakistan(self):
        label, score = eligibility(
            False, "Remote — US only", "Remote (US only)", ["pakistan"], {"apac"}
        )
        self.assertEqual(label, "location-locked")
        self.assertEqual(score, 0)

    def test_us_only_accepts_us(self):
        label = eligibility(
            True, "Remote — US only", "Remote (US only)", ["new york, usa"], {"us"}
        )
        self.assertEqual(label, "where you are")

    def test_worldwide(self):
        label = eligibility(True, "Work from anywhere", "Remote", ["pakistan"], {"apac"})
        self.assertEqual(label, "open worldwide")

    def test_emea_timezones_reject_apac(self):
        label = eligibility(
            True, "Must be based in EMEA time zones", "EMEA", ["pakistan"], {"apac"}
        )
        self.assertEqual(label, "location-locked")

    def test_no_sponsorship(self):
        label = eligibility(
            True, "We are unable to sponsor visas", "Remote", ["pakistan"], {"apac"}
        )
        self.assertEqual(label, "no sponsorship")


if __name__ == "__main__":
    unittest.main()
