"""Zero adoption must be checkable, not winnable by wording."""

import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestAdoption(unittest.TestCase):
    def test_the_checker_asks_four_parties(self):
        with open(os.path.join(REPO, "tools", "check_adoption.py"), encoding="utf-8") as fh:
            src = fh.read()
        for bucket in ("another repository", "another codebase", "a standards body",
                       "a neighbouring spec"):
            self.assertIn(bucket, src, "bucket %r disappeared from the adoption check" % bucket)

    def test_the_landscape_doc_does_not_claim_a_lead(self):
        with open(os.path.join(REPO, "docs", "LANDSCAPE-2026-11.md"), encoding="utf-8") as fh:
            doc = fh.read()
        self.assertIn("不是领先，是落后", doc,
                      "the landscape doc lost the sentence that keeps it honest")


if __name__ == "__main__":
    unittest.main()
