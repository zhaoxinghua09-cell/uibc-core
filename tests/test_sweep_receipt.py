"""The 512-leaf sweep left a receipt, and the receipt has to be checkable.

`verify_tree_algebra_exhaustive.py` printed "131,328 + 131,328, 0 disagreements"
on 2026-11-22. That sentence lived in a terminal, until this receipt bound the
counts to a digest of the instance file. The dump itself is 199 MB and is not
committed; the receipt records its size and digest, so the claim can be re-derived
by re-running the sweep (8m23s at 512) rather than taken on our word. What the
receipt cannot do is prove the sweep was run only once, and it says so.
"""

import json
import os
import subprocess
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RECEIPT = os.path.join(_REPO, "docs", "sweep-receipt-512.json")
CHECKER = os.path.join(_REPO, "tools", "check_sweep_receipt.py")


class SweepReceiptTest(unittest.TestCase):
    def test_the_receipt_checker_catches_its_own_mutations(self):
        r = subprocess.run([sys.executable, CHECKER, "--self-test"],
                           capture_output=True, text=True, cwd=_REPO)
        self.assertEqual(r.returncode, 0, r.stdout[-600:] + r.stderr[-400:])

    def test_the_committed_512_receipt_is_arithmetically_possible(self):
        with open(RECEIPT, encoding="utf-8") as fh:
            receipt = json.load(fh)
        self.assertEqual(receipt["max_size"], 512)
        n = 512 * 513 // 2
        self.assertEqual(receipt["inclusion_instances"], n)
        self.assertEqual(receipt["consistency_instances"], n)
        self.assertEqual(receipt["disagreements"], 0)
        self.assertEqual(len(receipt["dump_sha256"]), 64)
        self.assertGreater(receipt["dump_bytes"], 0)

    def test_the_receipt_is_checked_through_the_same_code_the_cli_runs(self):
        r = subprocess.run([sys.executable, CHECKER, RECEIPT],
                           capture_output=True, text=True, cwd=_REPO)
        self.assertEqual(r.returncode, 0, r.stdout[-400:])
        self.assertIn("SWEEP-RECEIPT-CONSISTENT", r.stdout)


if __name__ == "__main__":
    unittest.main()
