"""The incidence matrix exists to make two claims checkable.

1. Every check has been made to fire at least once -- otherwise it is
   untested decoration.
2. Most attacks move exactly one check -- otherwise "each check tests one
   thing" is a slogan rather than a measurement.
"""
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_matrix as cm


class TestCheckMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cm.build(cm.audit())

    def test_every_check_is_reachable_by_some_attack(self):
        self.assertEqual(self.d["unreached"], [], "a check no attack ever fires is decoration")

    def test_most_attacks_isolate_one_check(self):
        share = len(self.d["isolated"]) / self.d["n_attacks"]
        self.assertGreaterEqual(share, 0.80,
                                "too many attacks move several checks at once")

    def test_almost_every_attack_catches_something(self):
        self.assertGreaterEqual(self.d["n_caught"], self.d["n_attacks"] - 3)

    def test_coupled_attacks_are_recorded_not_hidden(self):
        multi = [r for r in self.d["rows"] if r["n"] > 1]
        self.assertTrue(multi, "expected at least one coupled attack to be documented")
        for r in multi:
            self.assertTrue(r["checks"], r["name"])

    def test_the_svg_marks_the_isolated_count(self):
        svg = cm.render_svg(self.d)
        self.assertIn(str(len(self.d["isolated"]), ), svg)

    def test_known_gap_is_labelled_not_silently_blank(self):
        blank = [r for r in self.d["rows"]
                 if not r["checks"] and r["got"] != "PASS"]
        svg = cm.render_svg(self.d)
        self.assertTrue(blank, "the tail-receipt gap should still be listed")
        self.assertIn("not caught", svg)


if __name__ == "__main__":
    unittest.main()
