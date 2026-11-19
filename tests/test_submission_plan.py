"""The plan must not read as aspiration once its first two steps are done."""

import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSubmissionPlan(unittest.TestCase):
    def test_done_steps_are_marked(self):
        with open(os.path.join(REPO, "docs", "UPSTREAM-SUBMISSION-PLAN.md"), encoding="utf-8") as fh:
            doc = fh.read()
        self.assertIn("Status: done, 2026-11-19", doc)
        self.assertIn("9a1ca72fea75f837", doc, "the published archive hash is no longer recorded")

    def test_unsent_steps_still_say_unsent(self):
        with open(os.path.join(REPO, "docs", "UPSTREAM-SUBMISSION-PLAN.md"), encoding="utf-8") as fh:
            doc = fh.read()
        self.assertIn("Steps 3 and 4 have not been sent", doc,
                      "the doc reads as if the outside steps had happened")


if __name__ == "__main__":
    unittest.main()
