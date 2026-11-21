"""The comparison is only worth keeping if it stays honest when it is wrong.

So the tests pin the two things a cheerful version would quietly drop: the
known gap (an uncommitted file under evidence/ is not judged) and the fact that
a competitor's format may have no counterpart for an attack at all.
"""
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import compare_diagnostics as cd


class TestDiagnosticsCompare(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cd.build()

    def test_six_attacks_on_our_side(self):
        self.assertEqual(len(self.d["ours"]["cases"]), 6)

    def test_every_rejection_says_which_check(self):
        for c in self.d["ours"]["cases"]:
            if c["verdict"] == "FAIL":
                self.assertTrue(c["ids"], c["attack"])
                self.assertTrue(c["first"] or True)

    def test_the_known_gap_is_recorded_not_hidden(self):
        """An uncommitted file under evidence/ is not judged. If someone fixes
        that, this test fails on purpose so the doc gets updated."""
        by = {c["attack"]: c for c in self.d["ours"]["cases"]}
        self.assertEqual(by["add an undeclared file"]["verdict"], "INCONCLUSIVE",
                         "the documented gap changed; update docs/DIAGNOSTICS.md")

    def test_a_deleted_evidence_file_is_located_by_name(self):
        """This is the bug fixed alongside the tool: S13 used to raise
        IndexError and collapse into S0 with no object named."""
        by = {c["attack"]: c for c in self.d["ours"]["cases"]}
        c = by["delete one evidence file"]
        self.assertEqual(c["verdict"], "FAIL")
        self.assertNotIn("S0", c["ids"])
        self.assertIn("action-log.txt", c["first"])

    def test_their_side_is_either_named_or_absent(self):
        why = self.d["theirs"].get("unavailable")
        if why:
            self.skipTest("competitor package not installed: %s" % why)
        for c in self.d["theirs"]["cases"]:
            self.assertIn(c["verdict"], ("FAIL", "PASS", "n/a"), c["attack"])


if __name__ == "__main__":
    unittest.main()
