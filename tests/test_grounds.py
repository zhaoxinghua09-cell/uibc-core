"""Grounds must be quotations, not quotation marks.

Each reject case in the corpus says what it rests on. Where the basis is a draft
clause, the clause is quoted and this test checks it is really in the vendored
draft. Where a check is draft-mandated but no clause has been located, the file
says `clause_absent` instead of quietly leaving the field out.
"""

import io
import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(HERE, "conformance", "oracle")

BASES = {"draft_mandated", "borrowed_idea", "own_choice"}


def _squash(text):
    return re.sub(r"\s+", " ", text).strip().replace("*", "")


class TestGrounds(unittest.TestCase):
    def setUp(self):
        self.grounds = json.load(io.open(os.path.join(CORPUS, "grounds.json"),
                                         encoding="utf-8"))["cases"]
        self.expected = json.load(io.open(os.path.join(CORPUS, "expected.json"),
                                          encoding="utf-8"))["cases"]

    def test_every_reject_case_says_what_it_rests_on(self):
        rejects = [c["case"] for c in self.expected
                   if c["kind"] != "accept" and c.get("expected_first_fail")]
        covered = {row["case"] for row in self.grounds}
        self.assertEqual(sorted(set(rejects)), sorted(covered),
                         "a reject case with no stated basis is an assertion")

    def test_every_basis_is_one_of_three_accountable_kinds(self):
        for row in self.grounds:
            self.assertIn(row["basis"], BASES, row["case"])

    def test_every_quoted_clause_is_actually_in_the_vendored_draft(self):
        checked = 0
        for row in self.grounds:
            if not row.get("clause_quote"):
                continue
            path = os.path.join(HERE, row["clause_source"])
            self.assertTrue(os.path.isfile(path), "%s cites a file not in the repo"
                            % row["case"])
            body = _squash(io.open(path, encoding="utf-8", errors="replace").read())
            quote = _squash(row["clause_quote"])
            self.assertIn(quote, body, "%s quotes a clause the draft does not contain"
                          % row["case"])
            checked += 1
        self.assertGreaterEqual(checked, 4, "grounds lost their quotations")

    def test_unlocated_clauses_are_declared_not_omitted(self):
        absent = [row["check"] for row in self.grounds if row.get("clause_absent")]
        self.assertEqual(absent, [],
                         "a draft-mandated check with no located clause must be "
                         "reclassified in uibc_core/basis.py, not shipped as absent")

    def test_grounds_follow_the_shipped_basis_table(self):
        """grounds.json is derived from uibc_core.basis; if the two disagree, one of
        them is telling a different story about the same check."""
        import sys
        repo = os.path.dirname(HERE)
        if repo not in sys.path:
            sys.path.insert(0, repo)
        from uibc_core.basis import BASIS
        kinds = {"direct": "draft_mandated", "related": "borrowed_idea",
                 "none": "own_choice"}
        for row in self.grounds:
            self.assertEqual(kinds[BASIS[row["check"]]["class"]], row["basis"],
                             "%s: basis table and corpus disagree" % row["check"])

    def test_own_choice_checks_never_claim_a_clause(self):
        for row in self.grounds:
            if row["basis"] == "own_choice":
                self.assertFalse(row.get("clause_quote"),
                                 "%s is our own choice and must not cite a draft"
                                 % row["case"])


if __name__ == "__main__":
    unittest.main()
