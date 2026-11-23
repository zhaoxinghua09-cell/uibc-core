# SPDX-License-Identifier: Apache-2.0
"""Two documents must keep saying what they say now.

`docs/CORPUS-DISCIPLINE.md` states six rules and, for each one, the defect we
shipped. `docs/INVITE-ONE-PAGE.md` asks an outside implementer to run the corpus;
it also states that it had not been sent when written. Both are claims about
ourselves, so both can decay: the invite could quietly be described as sent, and
the discipline page could quietly lose the defects it exists to document.

These tests are cheap and they only fail when someone rewrites the meaning.
"""
import os
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = os.path.join(REPO, "docs")


def _read(name):
    with open(os.path.join(DOCS, name), encoding="utf-8") as fh:
        return fh.read()


class TestDisciplinePageNamesTheDefects(unittest.TestCase):
    def test_six_rules_are_stated(self):
        doc = _read("CORPUS-DISCIPLINE.md")
        for n in range(1, 7):
            self.assertIn("## Rule %d —" % n, doc, "rule %d lost its heading" % n)

    def test_each_rule_names_a_real_defect(self):
        doc = _read("CORPUS-DISCIPLINE.md")
        # The page is only honest while it admits the defects it documents.
        self.assertIn("**What we violated.**", doc)
        self.assertIn("orphaned", doc)              # rule 1
        self.assertIn("CRLF", doc)                  # rule 2
        self.assertIn("underspecified_inputs", doc) # rule 3
        self.assertIn("class_counts", doc)          # rule 4
        self.assertIn("root equal", doc)            # rule 5
        self.assertIn("20 of 23", doc)               # rule 6

    def test_page_does_not_claim_superiority(self):
        doc = _read("CORPUS-DISCIPLINE.md").lower()
        for phrase in ("best-in-class", "state of the art", "world-leading",
                       "superior to every", "better than all"):
            self.assertNotIn(phrase, doc)


class TestInvitePageIsStillAnInvite(unittest.TestCase):
    def test_it_declares_not_yet_sent(self):
        doc = _read("INVITE-ONE-PAGE.md")
        self.assertIn("Not yet sent", doc)

    def test_it_states_the_author_independence_of_the_second_implementation(self):
        doc = _read("INVITE-ONE-PAGE.md")
        self.assertIn("second-party-same-code", doc)
        # The sentence wraps in the source, so match the fragment that does not.
        self.assertIn("never as an external", doc)

    def test_it_does_not_promise_endorsement_for_them(self):
        doc = _read("INVITE-ONE-PAGE.md")
        self.assertIn("do not endorse anything", doc)

    def test_it_points_at_the_harness_rather_than_asking_for_glue_code(self):
        # The invite used to end at "run your verifier over these files", which is a
        # request for laboour and is why the external-run axis stayed at zero.
        doc = _read("INVITE-ONE-PAGE.md")
        self.assertIn("conformance_harness.py", doc)
        self.assertIn("ADAPTER-PROTOCOL.md", doc)
        self.assertIn("wording only", doc)


if __name__ == "__main__":
    unittest.main()
