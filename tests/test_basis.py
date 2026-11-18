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


if __name__ == "__main__":
    unittest.main()
