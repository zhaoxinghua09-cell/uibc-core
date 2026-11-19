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

    def test_the_committed_matrix_is_what_the_tool_renders(self):
        """docs/CHECK-MATRIX.md drifted once: it had 18 columns while the run
        reached 19 checks, so the one artifact that proves coverage understated
        it. Regenerating by hand fixes the file until the next check is added;
        this test fixes the class of defect."""
        path = os.path.join(_REPO, "docs", "CHECK-MATRIX.md")
        with open(path, encoding="utf-8") as fh:
            on_disk = fh.read().replace("\r\n", "\n").strip()
        self.assertEqual(on_disk, cm.render_md(self.d).replace("\r\n", "\n").strip(),
                         "docs/CHECK-MATRIX.md is stale; regenerate with "
                         "`python tools/check_matrix.py > docs/CHECK-MATRIX.md`")

    def test_no_check_is_missing_from_the_columns(self):
        with open(os.path.join(_REPO, "docs", "CHECK-MATRIX.md"), encoding="utf-8") as fh:
            head = next(l for l in fh.read().splitlines() if l.startswith("| attack |"))
        cols = {c.strip() for c in head.strip("| ").split("|") if c.strip().startswith("S")}
        self.assertEqual(cols, set(self.d["checks"]),
                         "a check reached by an attack but absent from the table")


if __name__ == "__main__":
    unittest.main()
