"""Our JCS reproduces their listed table/pack digests, and the negatives too."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from uibc_core import canonical  # noqa: E402
import tools.crosscheck_aac_history_frame as cc  # noqa: E402


def _digest(v):
    return hashlib.sha256(canonical.canonicalize(v)).hexdigest()


class TestBindingVerdicts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        table = {"a": 1, "b": [2, 3]}
        pack = {"text": "hello"}
        cases = [
            {"id": "as-pinned", "inputs": {"table": table, "pack": pack,
             "listed": {"table": _digest(table), "pack": _digest(pack)}},
             "expected": {"properties": {"table_binding": "PASS", "pack_binding": "PASS"}}},
            {"id": "pack-swapped", "inputs": {"table": table, "pack": pack,
             "listed": {"table": _digest(table), "pack": _digest({"text": "other"})}},
             "expected": {"properties": {"table_binding": "PASS", "pack_binding": "FAIL"}}},
        ]
        self.path = os.path.join(self.tmp, "vectors.json")
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"cases": cases}, fh)

    def test_every_property_agrees(self):
        rows, bad = cc.run(self.path)
        self.assertEqual(len(rows), 4)
        self.assertEqual(bad, 0, rows)

    def test_cli(self):
        out = subprocess.run(
            [sys.executable, os.path.join(REPO, "tools", "crosscheck_aac_history_frame.py"),
             "--file", self.path], capture_output=True, text=True, cwd=REPO, timeout=60)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("disagreements: 0", out.stdout)


class TestTheCoverageNoteNowCountsTwo(unittest.TestCase):
    def _doc(self):
        with open(os.path.join(REPO, "docs", "COMPETITIVE-COVERAGE-AAC.md"),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_it_counts_two_classes(self):
        doc = self._doc()
        self.assertIn("history-frame-v0", doc)
        self.assertIn("22/22", doc)
        self.assertIn("5%", doc)

    def test_it_limits_the_second_class_to_binding(self):
        doc = self._doc()
        self.assertIn("不验证他们的计数规则", doc)


if __name__ == "__main__":
    unittest.main()
