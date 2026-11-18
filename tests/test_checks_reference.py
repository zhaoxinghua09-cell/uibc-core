"""The reference sheet is what a thesis appendix would quote, so it is held
like one: every check present, every question answered, and every external
basis classified rather than left to the reader's assumption."""

import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import build_checks_reference as bcr


class TestChecksReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = bcr.build()
        cls.by_id = {r["id"]: r for r in cls.rows}

    def test_every_check_is_described(self):
        import build_evidence_index as bei
        declared = bei.checks_declared()
        self.assertEqual(sorted(self.by_id), sorted(declared))

    def test_every_question_is_answered_in_words(self):
        """A blank question would make the table a list of ids, which is what
        the thesis appendix is supposed to replace."""
        for r in self.rows:
            self.assertTrue(r["question"], r["id"])
            self.assertRegex(r["question"], r"？$")

    def test_every_basis_is_classified(self):
        for r in self.rows:
            self.assertIn(r["basis_class"], ("direct", "related", "none"), r["id"])
            self.assertTrue(r["basis_note"], r["id"])

    def test_the_three_classes_are_all_present(self):
        classes = {r["basis_class"] for r in self.rows}
        self.assertEqual(classes, {"direct", "related", "none"})

    def test_no_check_claims_a_draft_it_does_not_name(self):
        """direct or related must name a document; nobody gets to say
        'per the standard' without saying which."""
        for r in self.rows:
            if r["basis_class"] != "none":
                self.assertRegex(r["basis_note"], r"(draft-|RFC )", r["id"])

    def test_the_doc_in_the_repo_matches_a_fresh_build(self):
        path = os.path.join(_REPO, "docs", "CHECKS-REFERENCE.md")
        with open(path, encoding="utf-8") as f:
            stored = f.read()
        self.assertEqual(stored, bcr.render(self.rows),
                         "docs/CHECKS-REFERENCE.md is stale; rerun the tool")


if __name__ == "__main__":
    unittest.main()
