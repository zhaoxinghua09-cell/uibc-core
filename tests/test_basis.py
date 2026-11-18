"""The basis field is a claim about the outside world, so it gets the same
scrutiny as the checks themselves: every check has one, only documented
classes carry a citation, and nothing invents a document."""
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core import basis


class TestBasis(unittest.TestCase):
    def test_every_check_has_a_basis(self):
        sys.path.insert(0, os.path.join(_REPO, "tools"))
        import build_evidence_index as bei  # noqa: E402
        declared = bei.checks_declared()
        for cid in declared:
            rec = basis.for_check(cid)
            self.assertIn(rec["class"], basis.CLASSES, cid)
            self.assertTrue(rec["note"], cid)

    def test_a_documented_class_names_a_document(self):
        for cid, rec in basis.BASIS.items():
            if rec["class"] in ("direct", "related"):
                self.assertRegex(rec["citation"], r"^(draft-|RFC )", cid)

    def test_an_undefined_rule_carries_no_citation(self):
        for cid, rec in basis.BASIS.items():
            if rec["class"] == "none":
                self.assertEqual(rec["citation"], "", cid)

    def test_unknown_ids_borrow_nothing(self):
        rec = basis.for_check("S99")
        self.assertEqual(rec["class"], "none")
        self.assertEqual(rec["citation"], "")

    def test_counts_match_the_classes(self):
        c = basis.counts()
        self.assertEqual(sum(c.values()), len(basis.BASIS))
        self.assertEqual(c["direct"] + c["related"] + c["none"], len(basis.BASIS))

    def test_the_report_carries_the_same_basis_as_the_module(self):
        from uibc_core.verify import verify
        r = verify(os.path.join(_REPO, "fixtures", "clean.uibc"))
        for c in r["checks"]:
            self.assertEqual(c["basis"]["class"], basis.for_check(c["id"])["class"], c["id"])


class TestExplainOutput(unittest.TestCase):
    """The human-facing view must carry the same citation the JSON field does,
    or the half-step this closed would reopen quietly."""

    def test_explain_prints_the_citation(self):
        import subprocess
        out = subprocess.run(
            [sys.executable, "-m", "uibc_core.cli", "explain",
             os.path.join(_REPO, "fixtures", "clean.uibc")],
            capture_output=True, text=True, cwd=_REPO, timeout=120)
        text = out.stdout
        self.assertIn("draft-noa-scitt-ai-agent-receipt-00", text)
        self.assertIn("本项目自定", text)
        self.assertIn("RFC 8785", text)

    def test_the_sentence_and_the_field_agree(self):
        import subprocess
        out = subprocess.run(
            [sys.executable, "-m", "uibc_core.cli", "verify",
             os.path.join(_REPO, "fixtures", "clean.uibc")],
            capture_output=True, text=True, cwd=_REPO, timeout=120)
        import json as _json
        report = _json.loads(out.stdout)
        for c in report["checks"]:
            if c["basis"]["class"] == "none":
                self.assertEqual(c["basis"]["citation"], "", c["id"])


if __name__ == "__main__":
    unittest.main()
