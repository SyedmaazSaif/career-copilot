"""Tests for the résumé-derived job scorer (backend/matching.py).

These lock in the profession-agnostic behaviour that motivated SCORE_VERSION 4:
a job that does not match the person's career must not earn points merely for
being remote or open-worldwide, the role component must not award free points
when there is no title to compare, and the score breakdown must sum to the
total shown to the user.
"""
import unittest

from backend.matching import SCORE_VERSION, seniority_band, score_job, tokenize


def profile(skills, title, past_titles, resume, user_band=None, home="Remote"):
    resume_text = " ".join([title, resume] + past_titles + skills)
    return {
        "skills": skills,
        "resume_text": resume_text,
        "resume_tokens": tokenize(resume_text),
        "target_titles": [title] + past_titles,
        "user_band": user_band,
        "preferred_arrangements": ["remote", "hybrid", "onsite"],
        "home_locations": [home.lower()],
        "has_resume": True,
    }


def job(title, description, location="Remote", tags=None):
    return {"title": title, "description": description, "location": location,
            "tags": tags or []}


WELDER = profile(
    ["MIG Welding", "TIG Welding", "Stick Welding", "Blueprint Reading",
     "Metal Fabrication"],
    "Welder", ["Fabricator", "Pipe Welder"],
    "Welder with 12 years experience in structural and pipe welding MIG TIG "
    "stick blueprint reading metal fabrication.",
)

ACCOUNTANT = profile(
    ["GAAP", "Tax Preparation", "Financial Statements", "QuickBooks"],
    "Tax Accountant", ["Staff Accountant", "Senior Accountant"],
    "Tax accountant GAAP tax preparation financial statements account "
    "reconciliation QuickBooks.",
    user_band=3,
)


class SeniorityBandTests(unittest.TestCase):
    def test_plain_title_has_no_band(self):
        self.assertEqual(seniority_band("Registered Nurse"), (None, None))

    def test_explicit_band_is_read(self):
        self.assertEqual(seniority_band("Senior Welder")[0], "senior")


class RoleComponentTests(unittest.TestCase):
    def test_no_title_overlap_scores_zero(self):
        # "Engineering Manager" shares no meaningful word with a welder's titles.
        res = score_job(
            job("Engineering Manager", "Own the notifications roadmap."), WELDER)
        self.assertEqual(res["reason"]["role"]["score"], 0)

    def test_generic_title_is_no_signal_not_half_match(self):
        # Every word in "Contract IT Specialist" is generic; it used to earn 10
        # free points and must now earn none.
        res = score_job(
            job("Contract IT Specialist", "Support internal systems."), WELDER)
        self.assertEqual(res["reason"]["role"]["score"], 0)

    def test_title_overlap_still_counts(self):
        res = score_job(job("Senior Tax Accountant", "Prepare returns."), ACCOUNTANT)
        self.assertGreater(res["reason"]["role"]["score"], 0)


class NoiseFloorTests(unittest.TestCase):
    def test_irrelevant_remote_job_scores_zero(self):
        # Pre-v4 this scored ~30 with zero relevance: "remote" and "no barrier
        # stated" added 17 points and the role floor added more. It must now
        # score zero, not look like a match.
        res = score_job(
            job("Engineering Manager",
                "Own the notifications roadmap. Ship features and mentor engineers."),
            WELDER,
        )
        self.assertEqual(res["score"], 0)

    def test_relevant_job_beats_irrelevant(self):
        relevant = score_job(
            job("Tax Accountant",
                "Prepare federal and state tax returns. Reconcile financial "
                "statements in QuickBooks. GAAP."),
            ACCOUNTANT,
        )
        irrelevant = score_job(
            job("Software Engineer", "Build web services with React and Node."),
            ACCOUNTANT,
        )
        self.assertGreater(relevant["score"], irrelevant["score"])

    def test_arrangement_still_ranks_relevant_jobs(self):
        # The scaling must not zero out arrangement for jobs that DO match: a
        # remote posting should still outrank the same role in a fixed city.
        desc = ("Prepare federal and state tax returns. Reconcile financial "
                "statements in QuickBooks. GAAP.")
        remote = score_job(job("Tax Accountant", desc, location="Remote"), ACCOUNTANT)
        city = score_job(job("Tax Accountant", desc, location="Dallas, TX"), ACCOUNTANT)
        self.assertGreater(remote["score"], city["score"])


class ScoreInvariantTests(unittest.TestCase):
    def test_breakdown_sums_to_total(self):
        for j in [
            job("Tax Accountant", "Prepare returns with GAAP and QuickBooks."),
            job("Engineering Manager", "Ship the notifications roadmap."),
        ]:
            res = score_job(j, ACCOUNTANT)
            r = res["reason"]
            total = (r["skills"]["score"] + r["role"]["score"]
                     + r["text"]["score"] + r["arrangement"]["score"]
                     + r["eligibility"]["score"])
            self.assertEqual(total, res["score"])

    def test_cold_start_is_provisional(self):
        cold = dict(WELDER, has_resume=False)
        res = score_job(job("Tax Accountant", "Prepare returns."), cold)
        self.assertTrue(res["reason"]["provisional"])


class VersionTests(unittest.TestCase):
    def test_score_version_bumped(self):
        # Any change to the rubric must bump this so old rows are rescored.
        self.assertGreaterEqual(SCORE_VERSION, 4)


if __name__ == "__main__":
    unittest.main()
