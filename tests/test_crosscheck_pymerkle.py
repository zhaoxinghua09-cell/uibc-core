# SPDX-License-Identifier: Apache-2.0
"""A third-party library must build the same roots the package claims.

The package's own verifier produced both the vectors and the verdicts, so on its
own it can only be internally consistent. This test hands the case files to
pymerkle (RFC 6962 mode), a library written elsewhere, and requires agreement on
the true root and on the VALID/INVALID split. It skips -- loudly -- when the
library is absent: a missing dependency must not silently turn into a pass.
"""
import importlib.util
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

try:
    import pymerkle  # noqa: F401
    HAVE_PYMERKLE = True
except ImportError:
    HAVE_PYMERKLE = False

TOOL = os.path.join(ROOT, "tools", "crosscheck_scitt_pymerkle.py")


def _load_tool():
    spec = importlib.util.spec_from_file_location("crosscheck_scitt_pymerkle", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAVE_PYMERKLE, "pymerkle not installed: third-party cross-check not run")
class ThirdPartyCrossCheck(unittest.TestCase):
    def test_the_library_agrees_on_every_case_it_can_read(self):
        mod = _load_tool()
        ok, report = mod.run()
        self.assertTrue(ok, json.dumps(
            {k: report[k] for k in ("cases_compared", "agrees_on_true_root",
                                    "agrees_on_verdict", "empty_tree_undefined_by_library")},
            ensure_ascii=False))
        self.assertGreater(report["cases_compared"], 40)
        self.assertEqual(report["agrees_on_true_root"], report["cases_compared"])
        self.assertEqual(report["agrees_on_verdict"], report["cases_compared"])
        # The empty-tree case is the one the library cannot read at all; it must be
        # reported as undefined rather than folded into the agreement count.
        self.assertEqual(report["empty_tree_undefined_by_library"], ["fail-empty-tree"])

        # Consistency cases: both endpoints' roots only. The two cases that declare
        # a deliberately wrong root must be the only places the library disagrees.
        cons = report["consistency"]
        self.assertEqual(cons["cases"], 13)
        self.assertEqual(cons["root_agreements"], 24)
        self.assertEqual(cons["mismatches"], [])
        self.assertEqual(cons["tampered_root_cases"],
                         ["cons-fail-new-root", "cons-fail-old-root"])

    def test_the_check_can_fail(self):
        # If mutating a leaf still "agrees everywhere", the comparison is vacuous.
        mod = _load_tool()
        InmemoryTree, _ = mod._load_lib()
        case = json.load(open(os.path.join(
            mod.CASE_DIR, "valid-tree16-index9", "expected.json"), encoding="utf-8"))
        leaves = mod._leaves_for(case, "valid-tree16-index9")
        leaves[0] = leaves[0] + b"mutation"
        tree = InmemoryTree(algorithm="sha256", mode="rfc6962")
        for leaf in leaves:
            tree.append_entry(leaf)
        self.assertNotEqual(mod._root_hex(tree), case["root_true"])


if __name__ == "__main__":
    unittest.main()
