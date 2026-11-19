"""The differential report must exist, carry both denominators, and say nothing
it cannot support.

This is the artifact that makes the project's one measurement claim checkable:
two implementations, hostile packages and clean packages, a false-pass count
and a false-alarm count. Every assertion below is a fact about the file, not a
score invented for a comparison table.

The report is deliberately *not* compared byte-for-byte with a fresh run: it
carries a timestamp and progress text, and a whole-file equality guard is the
environment check this repo already got burned by once. Structural invariants
plus a code-derived check count catch the drift that matters.
"""
import json
import os
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_REPORT = os.path.join(_REPO, "tools", "out", "differential-report.json")


class TestDifferentialReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(_REPORT, encoding="utf-8") as fh:
            cls.d = json.load(fh)

    def test_schema_is_declared(self):
        self.assertEqual(self.d["schema"], "uibc-differential/1")

    def test_the_false_pass_denominator_is_zero_and_stated(self):
        h = self.d["hostile"]
        self.assertEqual(h["false_pass"], 0, "a second implementation green-lighting a "
                                            "package the reference rejects")
        self.assertGreater(h["declined_to_judge"], 0,
                           "declining is the honest answer where it has no rule")
        self.assertEqual(h["false_pass"] + h["declined_to_judge"], 9,
                         "the 18 hostile packages must split between false pass and "
                         "declined; the remainder are correctly failed")

    def test_the_false_alarm_denominator_is_zero_and_stated(self):
        a = self.d["accept"]
        self.assertEqual(a["reference_false_alarms"], 0)
        self.assertEqual(a["independent_false_alarms"], 0)
        self.assertEqual(a["cases"], 9)

    def test_pairs_are_exact_and_unmapped_rules_are_not_called_coverage(self):
        self.assertEqual(self.d["exact_pairs_count"], 6)
        self.assertEqual(len(self.d["exact_pairs"]), self.d["exact_pairs_count"])
        self.assertEqual(sorted(self.d["unmapped_second_implementation_rules"]),
                         ["V7", "V8", "V9"])

    def test_the_check_count_is_the_code_not_a_snapshot(self):
        import uibc_core.basis as basis
        expected = len([c for c in basis.BASIS if c != "S0"])
        self.assertEqual(self.d["checks_total"], expected,
                         "the report's check count drifted from uibc_core/basis.py; "
                         "regenerate with `python tools/oracle_check.py --json-out "
                         "tools/out/differential-report.json`")

    def test_the_report_does_not_claim_agreement_it_never_measured(self):
        self.assertEqual(self.d["cells_disagreeing_with_the_oracle"], 0)
        self.assertEqual(self.d["verdict"], "PASS")
        for row in self.d["per_case"]:
            self.assertIn("independent_matches_oracle", row)
        # A case the second implementation cannot see is recorded as null, never True.
        for row in self.d["per_case"]:
            if row["independent_verdict"] == "n/a":
                self.assertIsNone(row["independent_matches_oracle"], row["case"])


if __name__ == "__main__":
    unittest.main()
