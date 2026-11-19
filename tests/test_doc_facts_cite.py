"""The suite size is counted once and cited everywhere else.

Background: eight documents used to carry the literal test count. Every parallel
branch rewrote the same eight lines, so every pull request collided on the same
eight lines. A number that has to be retyped in eight places is a number that
will be wrong in seven of them.

Now `docs/EVIDENCE-INDEX.md` publishes the count because a generator prints it,
and `check_doc_facts.py` rejects a typed count anywhere else.
"""

import os
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS = os.path.join(REPO, "tools")
for p in (REPO, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_doc_facts  # noqa: E402


class TestTypedCountsAreRejected(unittest.TestCase):
    def test_a_typed_count_is_a_mismatch_even_when_it_is_correct(self):
        """Correct today, wrong tomorrow: that is exactly the failure to prevent."""
        facts = {"tests": 639}
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write("The suite runs 639 tests on Linux.\n")
            path = fh.name
        try:
            bad = check_doc_facts.check(facts, [path])
        finally:
            os.unlink(path)
        self.assertEqual(len(bad), 1, "a typed test count was accepted")
        self.assertIn("cite", bad[0]["why"])


class TestTheIndexCarriesTheCount(unittest.TestCase):
    def test_index_number_matches_what_is_measured(self):
        facts = check_doc_facts.measure()
        with open(os.path.join(REPO, "docs", "EVIDENCE-INDEX.md"), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn("%d 个用例" % facts["tests"], page,
                      "the generated index no longer carries the measured count")


if __name__ == "__main__":
    unittest.main()
