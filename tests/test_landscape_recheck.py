"""The recheck note and the adoption-measurement note must stay honest.

These tests exist to fail if a later edit reintroduces the vocabulary the
2026-11-19 review took out: a superiority claim, a "first", or a document that
forgets it is a draft.
"""

import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO, "docs")


def _read(name):
    with open(os.path.join(DOCS, name), encoding="utf-8") as fh:
        return fh.read()


class TestRecheckNote(unittest.TestCase):
    def test_landscape_records_the_recheck_with_a_timestamp(self):
        doc = _read("LANDSCAPE-2026-11.md")
        self.assertIn("2026-11-19 复核", doc)
        self.assertRegex(doc, r"as of 2026-11-\d\dT\d\d:\d\d:\d\dZ")

    def test_landscape_separates_the_two_dimensions(self):
        doc = _read("LANDSCAPE-2026-11.md")
        self.assertIn("规格与生态", doc)
        self.assertIn("arXiv:2606.04193", doc)
        self.assertIn("in 2026, that adoption is zero", doc)


class TestAdoptionMeasurementNote(unittest.TestCase):
    def test_note_is_marked_unsent(self):
        doc = _read("ADOPTION-MEASUREMENT.md")
        self.assertIn("Status: draft, unsent", doc)

    def test_note_has_no_superiority_vocabulary(self):
        doc = _read("ADOPTION-MEASUREMENT.md")
        banned = [
            r"\bwe are stronger\b",
            r"\bwe are better\b",
            r"\bbest in class\b",
            r"\bworld[- ]leading\b",
            r"\bfully conformant\b",
        ]
        for pattern in banned:
            self.assertIsNone(re.search(pattern, doc, re.IGNORECASE),
                              "banned phrase came back: %s" % pattern)

    def test_note_states_its_own_limits(self):
        doc = _read("ADOPTION-MEASUREMENT.md")
        self.assertIn("cannot measure", doc)
        self.assertIn("What this method cannot measure", doc)


if __name__ == "__main__":
    unittest.main()
