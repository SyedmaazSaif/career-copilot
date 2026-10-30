"""Tests for the Jobicy source (fetch_jobs_vendored.fetch_jobicy).

Uses a saved real sample of the Jobicy API reply (tests/fixtures/jobicy.json)
so the parser is verified against real data, not invented shapes.
"""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.fetch_jobs_vendored import fetch_jobicy

FIXTURE = Path(__file__).parent / "fixtures" / "jobicy.json"


class _FakeResp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FetchJobicyTests(unittest.TestCase):
    def test_parses_real_jobs(self):
        payload = json.loads(FIXTURE.read_text())
        with patch("backend.fetch_jobs_vendored.requests.get") as get:
            get.return_value = _FakeResp(payload)
            jobs = fetch_jobicy()
        self.assertEqual(len(jobs), len(payload["jobs"]))
        for j in jobs:
            self.assertEqual(j["source"], "jobicy")
            self.assertTrue(j["title"])
            self.assertTrue(j["url"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
