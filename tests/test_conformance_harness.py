# SPDX-License-Identifier: Apache-2.0
"""The conformance harness must be able to fail, and must split roots from wording.

If the harness cannot produce a disagreement for an adapter that refuses nothing,
then a receipt from it means nothing. That is the same lesson as the 2026-10-22
gate fix, applied to the tool that collects outside reports.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

import tools.conformance_harness as h  # noqa: E402

HARNESS = os.path.join(REPO, "tools", "conformance_harness.py")


def _run(args, timeout=240):
    return subprocess.run([sys.executable, HARNESS] + args,
                          capture_output=True, text=True, cwd=REPO, timeout=timeout)


class TestPositiveControl(unittest.TestCase):
    def test_reference_adapter_agrees_on_every_root(self):
        out = _run(["--adapter", "%s %s" % (sys.executable,
                  os.path.join(REPO, "conformance", "adapters", "reference_python.py"))])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("ROOTS-AGREE", out.stdout)
        # Do not hard-code the vector count: the corpus is append-only and grew from
        # 30 to 41, which broke an earlier `assertIn("30/30")` without anything being
        # wrong. Read the two numbers out of the receipt and require them to be equal
        # and non-zero instead.
        m = re.search(r"root agreement\s*:\s*(\d+)/(\d+)", out.stdout)
        self.assertIsNotNone(m, out.stdout)
        agree, total = int(m.group(1)), int(m.group(2))
        self.assertGreater(total, 0, out.stdout)
        self.assertEqual(agree, total, out.stdout)

    def test_consistency_vectors_are_judged_not_skipped(self):
        # The harness crashed on the consistency half when it was added: it read
        # leaf_entry unconditionally. A corpus that the invite points outsiders at
        # has to run end to end, both halves, or "run our vectors" is a request that
        # fails halfway through.
        receipt = h.run([sys.executable, os.path.join(REPO, "conformance", "adapters",
                                                      "reference_python.py")])
        self.assertEqual(receipt["kinds"]["consistency"], 13)
        self.assertEqual(receipt["kinds"]["inclusion"], len(h.load_vectors()) - 13)
        self.assertEqual(receipt["root_agreement"], receipt["answered"])


class TestNegativeControl(unittest.TestCase):
    def test_accept_all_adapter_is_caught(self):
        out = _run(["--adapter", "%s %s" % (sys.executable,
                  os.path.join(REPO, "conformance", "adapters", "accept_all.py")),
                    "--expect-disagreement"])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("CONTROL-OK", out.stdout)
        self.assertIn("root mismatches", out.stdout)

    def test_a_verdict_wording_difference_is_not_a_conformance_failure(self):
        receipt = h.run([sys.executable, os.path.join(REPO, "conformance", "adapters",
                                                      "reference_python.py")])
        self.assertEqual(receipt["adapter_errors"], 0)
        self.assertEqual(receipt["root_agreement"], receipt["answered"])
        # The reference adapter says VALID / PROOF_DOES_NOT_VERIFY, we say
        # VALID / INVALID_*. Both root agreement and the split must show up.
        self.assertLess(receipt["verdict_agreement"], receipt["answered"])
        self.assertGreater(len(receipt["verdict_wording_only"]), 0)
        self.assertEqual(receipt["root_mismatches"], [])


class TestAdapterFailuresAreFindings(unittest.TestCase):
    def test_an_adapter_that_prints_nothing_is_an_adapter_error(self):
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "silent.py")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("import sys\nsys.exit(0)\n")
            out = _run(["--adapter", "%s %s" % (sys.executable, bad), "--only",
                        "valid-tree8-index2"], timeout=60)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("ADAPTER-BROKEN", out.stdout)

    def test_an_adapter_that_prints_non_json_is_an_adapter_error(self):
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "garbage.py")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("print('not json at all')\n")
            with self.assertRaises(RuntimeError):
                h.call_adapter([sys.executable, bad], h.load_vectors()[0]["request"])


class TestReceiptCarriesTheProvenance(unittest.TestCase):
    def test_receipt_names_command_environment_and_every_row(self):
        receipt = h.run([sys.executable, os.path.join(REPO, "conformance", "adapters",
                                                      "reference_python.py")],
                        vectors=h.load_vectors()[:2])
        self.assertEqual(receipt["schema"], "conformance-receipt/1")
        for key in ("adapter_command", "environment", "vectors", "rows", "how_to_read"):
            self.assertIn(key, receipt)
        self.assertEqual(len(receipt["rows"]), 2)
        self.assertIn("root_agreement", receipt["how_to_read"])
        self.assertIn("verdict_agreement", receipt["how_to_read"])


if __name__ == "__main__":
    unittest.main()
