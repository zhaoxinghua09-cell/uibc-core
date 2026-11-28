"""The comparison is a document, and documents drift.

These two tests do not touch the network - that is `tools/check_competitors.py`'s
job, and it is deliberately not in CI (an unauthenticated GitHub call is a
flaky gate, and a flaky gate teaches people to ignore gates). What is checkable
offline is that the recorded baseline is complete, and that the picture on the
front of it says what the baseline says.
"""
import json
import os
import unittest
import xml.etree.ElementTree as ET

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BASELINE = os.path.join(_REPO, "docs", "COMPETITORS.json")
_SVG = os.path.join(_REPO, "docs", "COMPETITORS.svg")


class TestCompetitorBaseline(unittest.TestCase):
    def test_the_baseline_records_both_projects(self):
        with open(_BASELINE, encoding="utf-8") as fh:
            d = json.load(fh)
        for side in ("ours", "peer"):
            self.assertIn(side, d)
            self.assertTrue(d[side].get("pypi_latest"), side + " has no version recorded")
            self.assertIsInstance(d[side].get("pypi_releases"), int, side)
        # A baseline with an error string instead of a number is a measurement
        # that failed and got written down as if it had succeeded.
        for side in ("ours", "peer"):
            self.assertNotIn("pypi_error", d[side])

    def test_the_picture_states_the_same_numbers(self):
        with open(_BASELINE, encoding="utf-8") as fh:
            d = json.load(fh)
        tree = ET.parse(_SVG)
        text = " ".join((t.text or "") for t in tree.iter()
                        if t.tag.endswith("text"))
        self.assertIn(str(d["ours"]["tests"]), text)
        self.assertIn(str(d["ours"]["pypi_releases"]), text)
        self.assertIn(str(d["peer"]["pypi_releases"]), text)
        self.assertIn(str(d["ours"]["conformance_cases"]), text)
        self.assertIn("agent-action-capsule", text)


if __name__ == "__main__":
    unittest.main()
