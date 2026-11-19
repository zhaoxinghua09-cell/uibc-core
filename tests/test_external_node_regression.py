"""The row an outsider found is watched by a check that can fail.

External node 001 reported two disagreements on `fixture:duplicated` (S4, S5).
If either returns, `tools/external_node_regression.py` must say REGRESSED and
`run_all_evidence.py` must go red - a check that cannot fail is decoration.
"""

import os
import subprocess
import sys
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS = os.path.join(REPO, "tools")
for p in (REPO, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import external_node_regression as enr  # noqa: E402


class TestTheCheckCanFail(unittest.TestCase):
    def test_a_mismatch_line_is_recognised(self):
        """The parser must see the exact shape the outsider's report had."""
        fake = ("fixture:duplicated   S4   V4   FAIL           PASS   MISMATCH\n"
                "fixture:duplicated   S5   V5   INCONCLUSIVE   FAIL   MISMATCH\n")
        rows = enr.rows_for(fake)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len([r for r in rows if "MISMATCH" in r]), 2)


class TestItHoldsToday(unittest.TestCase):
    def test_the_found_defect_has_not_returned(self):
        r = subprocess.run([sys.executable, os.path.join("tools", "external_node_regression.py")],
                           cwd=REPO, capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERDICT: STILL FIXED", r.stdout)
        # The limit must travel with the claim, not sit in a separate document.
        self.assertIn("does not establish that his run is reproducible today", r.stdout)


if __name__ == "__main__":
    unittest.main()
