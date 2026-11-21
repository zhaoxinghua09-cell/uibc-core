"""A run with no verifier must not be published as a 0/N result.

Found on 2026-11-20 by following docs/AUDIT-KIT.md exactly as a stranger would:
the archive ran, the verifier was not installed for that Python, and every case
came back FAIL with `reported: []`. The receipt said `0/36` and
`verifier_version: unknown`. Nothing in it distinguished "your packages are
broken" from "I never ran a verifier".

A stranger could publish that receipt in good faith, and it would read as "their
corpus fails every case". So run.py now refuses to write a receipt when no case
produced parseable output: exit 3, say why, name the interpreter and the install
command.

This test drives main() with rows that never parsed - the exact shape of that
failure - and asserts no receipt file appears.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO, "tools"))

import conformance_bundle_run as runner  # noqa: E402


def _rows(parsed, ok=None):
    ok = parsed if ok is None else ok
    out = []
    for i in range(1, 4):
        out.append({"id": "%02d" % i, "attack": "case %d" % i,
                    "ok": ok, "verdict": "FAIL" if parsed else "FAIL",
                    "reported": [], "expected": ["S4"],
                    "note": "" if parsed else "did not refuse a package that is broken",
                    "verifier_parsed": parsed,
                    "verifier_stderr": "" if parsed else "No module named 'uibc_core'"})
    return out


class TestNoReceiptWithoutAVerifier(unittest.TestCase):
    def setUp(self):
        # main() refuses to start without cases/ next to the script; the rows are
        # injected, so any directory satisfies that guard.
        self._cases = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self._cases, True))
        patcher = mock.patch.object(runner, "CASES", self._cases)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, rows, receipt_path):
        argv = ["run.py", "--verify", "nonexistent-verifier {pkg}",
                "--receipt", receipt_path]
        with mock.patch.object(runner, "run_all", return_value=rows), \
                mock.patch.object(sys, "argv", argv), \
                mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit) as ctx:
                runner.main()
        return ctx.exception.code

    def test_nothing_parsed_means_exit_3_and_no_receipt(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, True))
        target = os.path.join(tmp, "receipt.json")
        code = self._run(_rows(parsed=False), target)
        self.assertEqual(code, 3, "a run with no verifier must not exit 0 or 1")
        self.assertFalse(os.path.exists(target),
                         "a receipt saying 0/N would be published as a result")

    def test_a_real_verdict_still_writes_a_receipt(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, True))
        target = os.path.join(tmp, "receipt.json")
        argv = ["run.py", "--verify", "nonexistent-verifier {pkg}",
                "--receipt", target, "--json"]
        with mock.patch.object(runner, "run_all", return_value=_rows(parsed=True, ok=False)), \
                mock.patch.object(sys, "argv", argv), \
                mock.patch("sys.stdout"):
            with self.assertRaises(SystemExit) as ctx:
                runner.main()
        self.assertEqual(ctx.exception.code, 1, "3 failures should be exit 1")
        self.assertTrue(os.path.exists(target))

    def test_receipt_rows_carry_no_diagnostic_keys(self):
        """The published receipt keeps the same shape whoever runs it."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, True))
        target = os.path.join(tmp, "receipt.json")
        argv = ["run.py", "--verify", "nonexistent-verifier {pkg}",
                "--receipt", target]
        with mock.patch.object(runner, "run_all", return_value=_rows(parsed=True, ok=False)), \
                mock.patch.object(sys, "argv", argv), \
                mock.patch("sys.stdout"):
            with self.assertRaises(SystemExit):
                runner.main()
        import json
        with open(target, encoding="utf-8") as f:
            receipt = json.load(f)
        for row in receipt["rows"]:
            self.assertNotIn("verifier_parsed", row)
            self.assertNotIn("verifier_stderr", row)


if __name__ == "__main__":
    unittest.main()
