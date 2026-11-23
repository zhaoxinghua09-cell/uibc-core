# SPDX-License-Identifier: Apache-2.0
"""The package's audit paths must fold to the same roots under Sigstore's arithmetic.

pymerkle is asked to build trees from leaf texts; it never reads a proof path. This
test hands the paths to the vendored Sigstore folding code instead, so the claim
"our path arithmetic is met by a second implementation" has a command behind it.
"""
import importlib.util
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "tools", "crosscheck_scitt_sigstore.py")


def _load_tool():
    spec = importlib.util.spec_from_file_location("crosscheck_scitt_sigstore", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SigstoreCrossCheck(unittest.TestCase):
    def test_every_foldable_path_agrees(self):
        mod = _load_tool()
        ok, report = mod.run()
        self.assertTrue(ok, json.dumps({k: report[k] for k in (
            "cases_folded", "agrees_on_fold", "agrees_on_verdict",
            "refused_by_library", "empty_tree_has_no_path")}, ensure_ascii=False))
        self.assertTrue(report["cases_folded"] >= 40, report["cases_folded"])
        self.assertEqual(report["agrees_on_fold"], report["cases_folded"])
        self.assertEqual(report["agrees_on_verdict"], report["cases_folded"])
        # The seven the library refuses are the malformed-length paths; each is an
        # INVALID case in our package, so a refusal is agreement, not a gap.
        self.assertEqual(len(report["refused_by_library"]), 7)
        for name in report["refused_by_library"]:
            with open(os.path.join(mod.CASE_DIR, name, "expected.json"), encoding="utf-8") as fh:
                case = json.load(fh)
            self.assertTrue(case["result"].startswith("INVALID"), name)
        self.assertEqual(report["empty_tree_has_no_path"], ["fail-empty-tree"])

    def test_the_check_can_fail(self):
        mod = _load_tool()
        _, mutated = mod.run(mutate=1)
        self.assertGreater(mutated["mutated_paths_attempted"], 30)
        self.assertEqual(mutated["mutated_paths_detected"],
                         mutated["mutated_paths_attempted"])


if __name__ == "__main__":
    unittest.main()
