"""A receipt that cannot be quoted must be refused, not averaged in.

The point of docs/RECEIPT-FORMAT.md is that an outsider's number is only usable
if the file says where it came from. These tests hold the checker to that: six
ways a receipt can lie, all refused; one honest receipt, accepted.
"""
import hashlib
import json
import os
import subprocess
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO, "tools"))
import check_outward_receipt as chk  # noqa: E402


def _receipt(**over):
    rows = [{"id": "01", "attack": "clean", "ok": True, "verdict": "INCONCLUSIVE",
             "reported": [], "expected": [], "note": ""},
            {"id": "02", "attack": "flipped byte", "ok": True, "verdict": "FAIL",
             "reported": ["S4"], "expected": ["S4"], "note": ""}]
    base = {
        "kind": chk.KIND,
        "notice": "not a certification",
        "run_by": "A. Stranger <stranger@example.org>",
        "when_utc": "2026-11-20T03:04:05Z",
        "command": 'python3 "uibc_core.pyz" verify {pkg}',
        "python": "3.12.3",
        "platform": "Linux-6.8-x86_64",
        "verifier_version": "0.4.1",
        "manifest_sha256": "a" * 64,
        "cases": len(rows),
        "passed": len(rows),
        "rows": rows,
    }
    base.update(over)
    return base


class TestAnHonestReceiptIsAccepted(unittest.TestCase):
    def test_a_clean_receipt_passes(self):
        self.assertEqual(chk.check(_receipt()), [])

    def test_the_cli_returns_zero_and_says_acceptable(self):
        path = os.path.join(os.environ.get("TEMP", "/tmp"), "receipt_ok.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_receipt(), f)
        proc = subprocess.run([sys.executable, os.path.join(_REPO, "tools", "check_outward_receipt.py"), path],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("ACCEPTABLE", proc.stdout)


class TestItRefusesWhatCannotBeQuoted(unittest.TestCase):
    def test_unknown_verifier_version_is_refused(self):
        reasons = chk.check(_receipt(verifier_version="unknown"))
        self.assertTrue(any("did not name which verifier" in r for r in reasons), reasons)

    def test_a_summary_that_contradicts_its_rows_is_refused(self):
        reasons = chk.check(_receipt(passed=0))
        self.assertTrue(any("passed is 0" in r for r in reasons), reasons)

    def test_the_wrong_corpus_digest_is_refused(self):
        reasons = chk.check(_receipt(), expect_manifest_sha256="b" * 64)
        self.assertTrue(any("the corpus you mean" in r for r in reasons), reasons)

    def test_an_unattributed_receipt_is_refused_for_node_counting(self):
        reasons = chk.check(_receipt(run_by=""))
        self.assertTrue(any("no named runner" in r for r in reasons), reasons)
        self.assertEqual(chk.check(_receipt(run_by=""), require_run_by=False), [])

    def test_a_command_that_names_no_verifier_is_refused(self):
        reasons = chk.check(_receipt(command="python run.py"))
        self.assertTrue(any("names neither" in r for r in reasons), reasons)

    def test_a_timestamp_that_is_not_a_time_is_refused(self):
        reasons = chk.check(_receipt(when_utc="last tuesday"))
        self.assertTrue(any("when_utc" in r for r in reasons), reasons)


class TestTheFrontPageDoesNotRot(unittest.TestCase):
    def test_readme_points_at_the_archive_and_the_receipt_format(self):
        with open(os.path.join(_REPO, "README.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("docs/AUDIT-KIT.md", text)
        self.assertIn("docs/RECEIPT-FORMAT.md", text)
        self.assertIn("conformance/uibc-conformance-0.4.1.zip", text)

    def test_readme_quotes_the_archive_digest_it_actually_ships(self):
        """A stale digest on the front page is worse than no digest."""
        with open(os.path.join(_REPO, "conformance", "uibc-conformance-0.4.1.zip"), "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        with open(os.path.join(_REPO, "README.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn(digest[:8], text, "README quotes a digest the shipped archive does not have")


if __name__ == "__main__":
    unittest.main()
