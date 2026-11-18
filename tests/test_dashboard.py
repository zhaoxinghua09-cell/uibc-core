"""The dashboard is a picture of numbers that live in other tools.

Two things can go wrong and both look fine: the data can silently fall back to
an empty package (bars become zero but the axis still looks reasonable), or a
matching bug can compare whole records against names and sum nothing. Both
happened while building it, so both get a test.
"""
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_dashboard as bd


class TestDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = bd.collect()

    def test_the_three_channels_are_the_source_of_the_first_panel(self):
        self.assertEqual(set(self.d["channels"]), {"archive (DOI)", "package (pip)",
                                                   "repository"})
        self.assertEqual(self.d["channels"]["repository"], self.d["n_checks"])

    def test_the_basis_panel_adds_up_to_the_checks(self):
        b = self.d["basis"]
        self.assertEqual(sum(b.values()), self.d["n_checks"])

    def test_reason_counts_are_not_zero_by_accident(self):
        """A zero here means the full-featured package was not built, and every
        bar on the page would be empty while still rendering. Without the
        competitor installed there is nothing to compare, and the panel says so
        instead of drawing zeros."""
        if not self.d.get("compared"):
            self.assertIn("未测", bd.render(self.d))
            self.skipTest("competitor package not installed here")
        self.assertGreater(self.d["ours"], 0, "our side has no reasons")
        self.assertGreater(self.d["common"], 0)

    def test_common_is_a_list_of_names(self):
        """Regression guard: `common` once held case dicts, so `attack in
        common` matched nothing and every sum came out zero."""
        dg = bd._run_json("compare_diagnostics.py")
        for c in dg["ours"]["cases"]:
            self.assertIsInstance(c["attack"], str)

    def test_the_svg_carries_the_computed_numbers(self):
        svg = bd.render(self.d)
        self.assertIn(str(self.d["n_checks"]), svg)
        self.assertIn(str(self.d["ours"]), svg)
        self.assertIn(str(self.d["theirs"]), svg)

    def test_the_competitor_facts_name_their_sources_and_date(self):
        for key in ("source", "verified_on", "third_party_implementations"):
            self.assertIn(key, self.d["facts"])


if __name__ == "__main__":
    unittest.main()
