"""The outsider's receipt must be recomputable here, not just quoted.

`EXTERNAL-NODE-001.md` quotes 605 tests and 2 mismatches from a host we do not
control. If we could not reproduce those figures, we would be publishing hearsay
under the heading "third-party evidence". This tool recomputes them; the tests
below hold it to that job.

`--quick` skips the 605-test run (about a minute) and checks the comparison
figures only; the full run is exercised when the tool is called without it.
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

import verify_external_node_report as v  # noqa: E402


class TestTheReceiptIsPinned(unittest.TestCase):
    def test_the_quoted_figures_come_from_the_report_itself(self):
        """If the doc says 605 and the tool expects 606, the test should see it."""
        doc = os.path.join(REPO, "docs", "external-review", "EXTERNAL-NODE-001.md")
        with open(doc, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("Ran %d tests" % v.RECEIPT_TESTS, text,
                      "the tool and the receipt disagree on the test count")
        self.assertIn("mismatches: %d" % v.RECEIPT_MISMATCHES, text,
                      "the tool and the receipt disagree on the mismatch count")

    def test_parsers_read_the_two_line_shapes(self):
        out = ("Ran 605 tests in 61.8s\n\n"
               "checks compared: 70, mismatches: 2\nAGREEMENT: FAIL - SPEC BUG\n")
        self.assertEqual(int(v.TESTS_RE.search(out).group(1)), 605)
        m = v.MISMATCH_RE.search(out)
        self.assertEqual((int(m.group(1)), int(m.group(2))), (70, 2))


def _has_ref(ref):
    r = subprocess.run(["git", "cat-file", "-e", ref + "^{commit}"], cwd=REPO,
                       capture_output=True, text=True)
    return r.returncode == 0


class TestItRecomputes(unittest.TestCase):
    def test_quick_run_matches_the_receipt(self):
        if not _has_ref(v.RECEIPT_REF):
            # A shallow clone cannot name the commit the receipt refers to. That is
            # a missing input, not a passing test: say so and let CI report it as
            # skipped, with the reason carrying the fix (`fetch-depth: 0`).
            self.skipTest("shallow clone: %s not present; ci.yml uses fetch-depth: 0"
                          % v.RECEIPT_REF)
        r = subprocess.run([sys.executable, os.path.join("tools", "verify_external_node_report.py"),
                            "--quick"], cwd=REPO, capture_output=True, text=True, timeout=900)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERDICT: MATCHES THE RECEIPT", r.stdout)
        # The scope sentence must travel with the verdict, not sit in a document.
        self.assertIn("It does not show his host behaved like ours", r.stdout)


if __name__ == "__main__":
    unittest.main()
