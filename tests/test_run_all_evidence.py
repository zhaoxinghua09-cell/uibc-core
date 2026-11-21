"""One command must keep being the way to check all seven claims."""

import os
import re
import unittest
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestEvidenceRun(unittest.TestCase):
    def test_the_runner_lists_every_check_the_docs_claim(self):
        with open(os.path.join(REPO, "tools", "run_all_evidence.py"), encoding="utf-8") as fh:
            src = fh.read()
        block = src.split("CHECKS = [")[1].split("\n]")[0]
        rows = [l for l in block.splitlines() if l.strip().startswith("(")]
        self.assertEqual(len(rows), 9, "the runner and the docs disagree on how many checks there are")

    def test_the_dashboard_has_a_row_per_check(self):
        tree = ET.parse(os.path.join(REPO, "docs", "EVIDENCE-DASHBOARD.svg"))
        dots = [e for e in tree.iter() if e.tag.endswith("circle")]
        self.assertEqual(len(dots), 9, "the picture and the runner disagree on how many checks there are")


if __name__ == "__main__":
    unittest.main()
