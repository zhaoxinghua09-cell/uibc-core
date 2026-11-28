"""A citation is a promise that the link leads to the thing described.

The archived 0.2.1 verifier implements six checks; the tree implements nineteen.
These tests hold the statement of that scope in place, because the convenient
version of this problem -- quietly bump the version string -- is the one that
would make a reader's download disagree with our claim.
"""

import json
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import check_citation_scope as ccs


class TestArchiveScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = ccs.build()
        with open(os.path.join(_REPO, "docs", "ARCHIVE-BASELINE.json"),
                  encoding="utf-8") as f:
            cls.baseline = json.load(f)

    def test_the_baseline_is_a_measurement_not_an_assertion(self):
        self.assertEqual(len(self.baseline["verify_py_sha256"]), 64)
        self.assertEqual(self.baseline["verify_py_lines"], 167)
        self.assertIn("how_measured", self.baseline)
        self.assertTrue(self.baseline["limits_of_this_measurement"])

    def test_the_archive_has_six_checks(self):
        self.assertEqual(self.r["archived_checks"],
                         ["S1", "S2", "S3", "S4", "S5", "S6"])

    def test_fourteen_ids_are_not_in_the_archive(self):
        unsupported = self.r["not_supported_by_the_doi"]
        for cid in ("S7", "S8", "S9", "S10", "S13", "S16", "S18", "S19"):
            self.assertIn(cid, unsupported)
        self.assertEqual(len(unsupported), 14)  # S0 plus S7-S19

    def test_nothing_vanished(self):
        self.assertEqual(self.r["checks_that_vanished"], [])

    def test_the_cff_states_the_scope(self):
        """If someone reverts the message to a bare version string, the
        misleading citation comes back."""
        with open(os.path.join(_REPO, "CITATION.cff"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("SCOPE", text)
        self.assertRegex(text, r"six checks")
        self.assertIn("S7-S19", text)
        self.assertIn("ARCHIVE-GAP.md", text)

    def test_the_cff_still_pins_the_archived_version(self):
        """Bumping the version here without a new archive would claim the DOI
        covers checks it does not contain. It is bumped here, to 0.5.5, because
        a new archive was actually published and measured (2026-11-26)."""
        self.assertRegex(text_of(os.path.join(_REPO, "CITATION.cff")),
                         r'version:\s*"0\.5\.5"')
        self.assertIn("10.5281/zenodo.24551514", text_of(os.path.join(_REPO, "CITATION.cff")))
        self.assertIn("10.5281/zenodo.24375013", text_of(os.path.join(_REPO, "CITATION.cff")))
        self.assertIn("10.5281/zenodo.22821835", text_of(os.path.join(_REPO, "CITATION.cff")))

    def test_the_doc_states_the_measured_numbers(self):
        path = os.path.join(_REPO, "docs", "ARCHIVE-GAP.md")
        with open(path, encoding="utf-8") as f:
            doc = f.read()
        self.assertIn("167", doc)
        self.assertIn("954", doc)


class TestTheGapIsClosed(unittest.TestCase):
    """A second archive now exists. The point of these tests is that closure is
    a measurement too: the baseline records the hash of the verifier inside the
    downloaded archive, and the tool must report zero unsupported checks
    against it."""

    @classmethod
    def setUpClass(cls):
        cls.path = os.path.join(_REPO, "docs", "ARCHIVE-BASELINE-0.4.2.json")
        with open(cls.path, encoding="utf-8") as f:
            cls.baseline = json.load(f)
        cls.r = ccs.build(cls.path)

    def test_the_new_baseline_is_also_a_measurement(self):
        self.assertEqual(len(self.baseline["verify_py_sha256"]), 64)
        self.assertEqual(self.baseline["verify_py_bytes"], 69835)
        self.assertTrue(self.baseline["limits_of_this_measurement"])

    def test_the_new_archive_carries_every_current_check(self):
        self.assertEqual(self.r["not_supported_by_the_doi"], [])
        self.assertEqual(self.r["checks_that_vanished"], [])
        for cid in ("S7", "S12", "S16", "S19"):
            self.assertIn(cid, self.r["supported_by_the_doi"])

    def test_the_old_baseline_is_still_honest_about_itself(self):
        old = ccs.build(os.path.join(_REPO, "docs", "ARCHIVE-BASELINE.json"))
        self.assertEqual(old["counts"]["archived"], 6)
        self.assertIn("S19", old["not_supported_by_the_doi"])

    def test_the_doc_records_the_closure_with_its_limits(self):
        doc = text_of(os.path.join(_REPO, "docs", "ARCHIVE-GAP.md"))
        self.assertIn("10.5281/zenodo.24375013", doc)
        self.assertIn("不能背书什么", doc)


def text_of(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    unittest.main()
