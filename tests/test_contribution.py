"""The offer to third parties must keep the same terms the suite enforces here."""

import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestContribution(unittest.TestCase):
    def test_the_contract_states_the_json_shape(self):
        with open(os.path.join(REPO, "docs", "CONTRIBUTION-FALSIFIABILITY.md"), encoding="utf-8") as fh:
            doc = fh.read()
        self.assertIn('"checks"', doc, "the verifier contract no longer names the checks field")
        self.assertIn("--name", doc, "the doc no longer tells a third party how to label their result")

    def test_the_accept_half_is_explained(self):
        with open(os.path.join(REPO, "docs", "CONTRIBUTION-FALSIFIABILITY.md"), encoding="utf-8") as fh:
            doc = fh.read()
        self.assertIn("refuses everything", doc,
                      "the doc lost the reason the accept half exists")


if __name__ == "__main__":
    unittest.main()
