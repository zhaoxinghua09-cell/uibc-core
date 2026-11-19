"""Running another project's nesting vectors against our reader.

The vectors are not vendored (they belong to another repository), so the run
uses a local fixture with the same shape: text of a given depth, must-accept
flag, and JCS digest for accepted text.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from uibc_core import canonical  # noqa: E402
import tools.crosscheck_aac_json_nesting as cc  # noqa: E402


def _text(depth):
    return "[" * depth + "]" * depth


class TestNestingLimit(unittest.TestCase):
    def test_depth_counts_brackets_not_characters(self):
        self.assertEqual(canonical.nesting_depth(1), 0)
        self.assertEqual(canonical.nesting_depth([]), 1)
        self.assertEqual(canonical.nesting_depth([[]]), 2)
        self.assertEqual(canonical.nesting_depth({"a": [{}]}), 3)

    def test_at_limit_is_accepted_and_past_is_refused(self):
        import json as _j
        obj = _j.loads(_text(canonical.MAX_NESTING_DEPTH))
        self.assertIsInstance(canonical.canonicalize(obj), bytes)
        deeper = _j.loads(_text(canonical.MAX_NESTING_DEPTH + 1))
        with self.assertRaises(ValueError):
            canonical.canonicalize(deeper)

    def test_string_brackets_do_not_count(self):
        obj = ["[[[[[[[["]
        self.assertEqual(canonical.nesting_depth(obj), 1)
        canonical.canonicalize(obj)


class TestCrosscheckTool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        cases = []
        for cid, depth, accept in (("pos-128", 128, True),
                                   ("neg-129", 129, False)):
            text = _text(depth)
            c = {"id": cid, "depth": depth, "accept": accept, "json": text}
            if accept:
                import hashlib
                c["jcs_sha256"] = hashlib.sha256(
                    canonical.canonicalize(json.loads(text))).hexdigest()
            cases.append(c)
        with open(os.path.join(self.tmp, "cases.json"), "w", encoding="utf-8") as fh:
            json.dump({"max_nesting_depth": 128, "cases": cases}, fh)

    def test_it_agrees_with_the_fixture(self):
        rows, bad = cc.run(self.tmp)
        self.assertEqual(bad, 0, rows)

    def test_cli_exit_code(self):
        out = subprocess.run(
            [sys.executable, os.path.join(REPO, "tools", "crosscheck_aac_json_nesting.py"),
             "--dir", self.tmp], capture_output=True, text=True, cwd=REPO, timeout=60)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


class TestTheCoverageNote(unittest.TestCase):
    def _doc(self):
        with open(os.path.join(REPO, "docs", "COMPETITIVE-COVERAGE-AAC.md"),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_it_states_the_coverage_fraction(self):
        doc = self._doc()
        self.assertIn("40", doc)
        self.assertIn("5%", doc)

    def test_it_says_the_limit_was_added_not_original(self):
        doc = self._doc()
        self.assertIn("必须写\"补齐的\"", doc)

    def test_it_keeps_the_first_disagreement(self):
        doc = self._doc()
        self.assertIn("mismatches: 4", doc)


if __name__ == "__main__":
    unittest.main()
