"""Tests for the company-by-name source resolver (settings.resolve_source)."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.routers.settings import resolve_source
from backend.schemas import SourceResolveIn


class ResolveSourceTests(unittest.TestCase):
    def test_greenhouse(self):
        with patch(
            "backend.routers.settings.find_company_site",
            return_value="https://boards.greenhouse.io/stripe",
        ) as fcs, patch(
            "backend.routers.settings._detect_ats", return_value=("greenhouse", "stripe")
        ):
            out = resolve_source(SourceResolveIn(name="Stripe"))
        self.assertTrue(out.found)
        self.assertEqual(out.kind, "greenhouse")
        self.assertEqual(out.value, "stripe")
        fcs.assert_called_once_with("", "Stripe")

    def test_generic_careers_page(self):
        with patch(
            "backend.routers.settings.find_company_site",
            return_value="https://stripe.com/jobs",
        ), patch(
            "backend.routers.settings._detect_ats", return_value=(None, None)
        ):
            out = resolve_source(SourceResolveIn(name="Stripe"))
        self.assertTrue(out.found)
        self.assertEqual(out.kind, "company")
        self.assertEqual(out.value, "https://stripe.com/jobs")

    def test_not_found(self):
        with patch("backend.routers.settings.find_company_site", return_value=None):
            out = resolve_source(SourceResolveIn(name="Some Unknown Co"))
        self.assertFalse(out.found)

    def test_empty_name_rejected(self):
        with self.assertRaises(HTTPException):
            resolve_source(SourceResolveIn(name="   "))


if __name__ == "__main__":
    unittest.main()
