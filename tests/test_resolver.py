"""Tests for the direct-link resolver (pure helpers + mocked network)."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.blocklist import is_blocked
from backend.resolver import (
    ResolveResult,
    _search_careers_page,
    _search_job,
    build_slugs,
    locations_compatible,
    resolve_job,
    title_matches,
    verify_direct_link,
)


class _Resp:
    def __init__(self, status_code=200, text="", url="https://example.com"):
        self.status_code = status_code
        self.text = text
        self.url = url


class BlocklistTests(unittest.TestCase):
    def test_blocks_aggregators(self):
        self.assertTrue(is_blocked("https://www.linkedin.com/jobs/view/123"))
        self.assertTrue(is_blocked("https://www.indeed.co.uk/job?jk=1"))
        self.assertTrue(is_blocked("https://remoteok.com/remote-jobs/1"))
        self.assertTrue(is_blocked("https://himalayas.app/companies/x/jobs/y"))

    def test_allows_ats_and_company_sites(self):
        self.assertFalse(is_blocked("https://boards.greenhouse.io/stripe/jobs/1"))
        self.assertFalse(is_blocked("https://jobs.lever.co/stripe/abc"))
        self.assertFalse(is_blocked("https://www.stripe.com/jobs/1"))


class SlugTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(build_slugs("Stripe"), ["stripe"])

    def test_strips_legal_suffixes(self):
        slugs = build_slugs("New Relic Inc.")
        self.assertIn("new-relic", slugs)
        self.assertIn("newrelic", slugs)
        self.assertNotIn("inc", " ".join(slugs))

    def test_empty(self):
        self.assertEqual(build_slugs(""), [])
        self.assertEqual(build_slugs("  "), [])


class TitleMatchTests(unittest.TestCase):
    def test_contained(self):
        self.assertTrue(title_matches("Senior Product Manager", "Product Manager"))
        self.assertTrue(title_matches("Sales Manager (Dubai)", "Sales Manager"))

    def test_exact(self):
        self.assertTrue(title_matches("Software Engineer", "Software Engineer"))

    def test_unrelated(self):
        self.assertFalse(title_matches("Software Engineer", "Data Scientist"))


class LocationTests(unittest.TestCase):
    def test_remote_is_compatible(self):
        self.assertTrue(locations_compatible("Remote", "New York"))

    def test_different_cities_conflict(self):
        self.assertFalse(locations_compatible("New York", "London"))


class VerifyTests(unittest.TestCase):
    def test_ok(self):
        with patch(
            "backend.resolver.requests.get",
            return_value=_Resp(200, "<html>Hiring a Senior Product Manager now</html>"),
        ):
            self.assertTrue(
                verify_direct_link(
                    "https://boards.greenhouse.io/x/y", "Senior Product Manager"
                )
            )

    def test_not_found(self):
        with patch("backend.resolver.requests.get", return_value=_Resp(404)):
            self.assertFalse(verify_direct_link("https://boards.greenhouse.io/x/y", "X"))

    def test_closed_page(self):
        with patch(
            "backend.resolver.requests.get",
            return_value=_Resp(200, "<html>This job has been closed</html>"),
        ):
            self.assertFalse(verify_direct_link("https://boards.greenhouse.io/x/y", "X"))

    def test_blocked_domain_skipped(self):
        # linkedin is blocked, so verification fails before any request.
        self.assertFalse(verify_direct_link("https://www.linkedin.com/jobs/view/1", "X"))


class SearchJobTests(unittest.TestCase):
    def test_rejects_mirror_site_with_company_in_path(self):
        # A mirror site that embeds the company in its URL path must be rejected
        # in favour of the company's own domain.
        mirror = "https://campusbuilding.com/company/birdeye/jobs/1"
        company_site = "https://birdeye.com/careers/"
        with patch(
            "backend.resolver._search_candidates",
            return_value=[mirror, company_site],
        ), patch("backend.resolver.verify_direct_link", return_value=True):
            self.assertEqual(
                _search_job("Birdeye", "Senior Product Manager"), company_site
            )

    def test_accepts_known_ats_domain(self):
        ats = "https://ats.rippling.com/birdeye-inc/jobs/abc"
        with patch(
            "backend.resolver._search_candidates", return_value=[ats]
        ), patch("backend.resolver.verify_direct_link", return_value=True):
            self.assertEqual(
                _search_job("Birdeye", "Senior Product Manager"), ats
            )

    def test_careers_page_rejects_mirror(self):
        mirror = "https://jobera.com/employer/committee-for-children/"
        company_site = "https://www.cfchildren.org/careers/"
        with patch(
            "backend.resolver._search_candidates",
            return_value=[mirror, company_site],
        ):
            self.assertEqual(
                _search_careers_page("Committee for Children"), company_site
            )


class ResolveJobTests(unittest.TestCase):
    def _job(self, url, company="Stripe", title="Product Manager", location="Remote"):
        return SimpleNamespace(
            url=url, company=company, title=title, location=location, id=1
        )

    def test_source_field_when_url_already_direct(self):
        url = "https://boards.greenhouse.io/stripe/jobs/1"
        result = resolve_job(None, self._job(url))
        self.assertEqual(result.link_type, "direct_job")
        self.assertEqual(result.resolved_via, "source_field")
        self.assertEqual(result.direct_url, url)

    def test_redirect_success(self):
        with patch(
            "backend.resolver._follow_redirect_to_direct",
            return_value=("https://jobs.lever.co/stripe/1", True),
        ), patch("backend.resolver._ats_lookup", return_value=None):
            result = resolve_job(
                None, self._job("https://www.linkedin.com/jobs/view/1")
            )
        self.assertEqual(result.link_type, "direct_job")
        self.assertEqual(result.resolved_via, "redirect")

    def test_ats_lookup_success(self):
        with patch(
            "backend.resolver._follow_redirect_to_direct", return_value=(None, False)
        ), patch(
            "backend.resolver._ats_lookup",
            return_value="https://boards.greenhouse.io/stripe/jobs/9",
        ):
            result = resolve_job(
                None, self._job("https://remoteok.com/remote-jobs/1")
            )
        self.assertEqual(result.link_type, "direct_job")
        self.assertEqual(result.resolved_via, "ats")

    def test_nothing_found(self):
        with patch(
            "backend.resolver._follow_redirect_to_direct", return_value=(None, False)
        ), patch("backend.resolver._ats_lookup", return_value=None), patch(
            "backend.resolver._search_job", return_value=None
        ), patch(
            "backend.resolver._search_careers_page", return_value=None
        ):
            result = resolve_job(
                None, self._job("https://www.linkedin.com/jobs/view/1")
            )
        self.assertEqual(result.link_type, "original")
        self.assertEqual(result.resolved_via, "none")
        self.assertIsNone(result.direct_url)


if __name__ == "__main__":
    unittest.main()
