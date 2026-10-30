"""Connector parsing tests against saved real responses (tests/fixtures/)."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.aggregators import fetch_hackernews, fetch_muse
from backend.ats import fetch_workable

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


class WorkableTests(unittest.TestCase):
    def test_parses_jobs(self):
        with patch("backend.ats.get_json", return_value=_load("workable.json")):
            jobs = fetch_workable("1password")
        self.assertGreaterEqual(len(jobs), 1)
        j = jobs[0]
        self.assertTrue(j["title"])
        self.assertTrue(j["company"])
        self.assertTrue(j["url"].startswith("https://"))
        self.assertEqual(j["source"], "workable:1password")


class MuseTests(unittest.TestCase):
    def test_parses_jobs(self):
        with patch("backend.aggregators.get_json", return_value=_load("muse.json")):
            jobs = fetch_muse()
        self.assertGreaterEqual(len(jobs), 1)
        j = jobs[0]
        self.assertTrue(j["title"])
        self.assertTrue(j["company"])
        self.assertTrue(j["url"].startswith("https://"))


class HackerNewsTests(unittest.TestCase):
    def test_parses_comments(self):
        story = {"objectID": "1", "title": "Ask HN: Who is hiring?", "created_at": "2026-10-01"}
        items = _load("hackernews.json")

        def fake_get_json(url, params=None, **kwargs):
            if "/items/" in url:
                return items
            return {"hits": [story]}

        with patch("backend.aggregators.get_json", side_effect=fake_get_json):
            jobs = fetch_hackernews()
        self.assertGreaterEqual(len(jobs), 1)
        self.assertTrue(all(j["title"] for j in jobs))
        self.assertTrue(all(j["source"] == "hackernews" for j in jobs))


if __name__ == "__main__":
    unittest.main()
