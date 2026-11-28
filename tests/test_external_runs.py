"""The external-run table must be a file that can refuse something.

`docs/RUNS.md` stated the rules in prose for a long time, and prose cannot fail.
These tests are the failing part: they assert that the committed table is
well-formed, and that four of the rules stop being true if the file is edited the
way the survey of 2026-11-22 showed a neighbouring ledger could be edited --
eight rows all called "independent" while its own field marked two blind and six
directed.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))
import check_external_runs as cx  # noqa: E402

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TABLE = os.path.join(_REPO, "docs", "EXTERNAL-RUNS.json")


class ExternalRunsTableTest(unittest.TestCase):
    def test_the_committed_table_passes(self):
        ok, msgs = cx.check(TABLE)
        self.assertTrue(ok, msgs)

    def test_the_committed_table_does_not_count_what_it_does_not_have(self):
        with open(TABLE, encoding="utf-8") as fh:
            doc = json.load(fh)
        want = cx.tally(doc["runs"])
        self.assertEqual(doc["counts"], want)
        # Zero is the honest number today; the test fails the day anyone raises
        # the headline without adding rows that support it.
        self.assertEqual(doc.get("headline", 0), want["blind_independent"])

    def test_a_row_calling_itself_independent_is_refused(self):
        doc = cx._sample()
        doc["runs"][0]["evidence"] = "independent"
        ok, msgs = cx.check_doc(doc)
        self.assertFalse(ok)
        self.assertTrue(any("not a kind, it is a conclusion" in m for m in msgs), msgs)

    def test_a_blind_claim_that_read_our_vectors_is_refused(self):
        doc = cx._sample()
        doc["runs"][0]["evidence"] = "blind"
        doc["runs"][0]["read_our_vectors"] = True
        ok, msgs = cx.check_doc(doc)
        self.assertFalse(ok)
        self.assertTrue(any("called blind yet records having read" in m for m in msgs), msgs)

    def test_a_normalised_figure_is_refused(self):
        doc = cx._sample()
        doc["runs"][0]["figure"] = "61 of 63 (97%)"
        ok, msgs = cx.check_doc(doc)
        self.assertFalse(ok)
        self.assertTrue(any("not verbatim n/n" in m for m in msgs), msgs)

    def test_a_tally_above_the_rows_is_refused(self):
        doc = cx._sample()
        doc["counts"]["blind"] = 1
        ok, msgs = cx.check_doc(doc)
        self.assertFalse(ok)
        self.assertTrue(any("counts[blind]" in m for m in msgs), msgs)

    def test_an_empty_table_is_accepted_because_empty_is_a_fact(self):
        # The refusal is of claims, not of absence. A checker that demanded rows
        # would push the next person to invent one.
        doc = {"contract_version": cx.CONTRACT, "runs": [], "headline": 0}
        doc["counts"] = cx.tally([])
        ok, msgs = cx.check_doc(doc)
        self.assertTrue(ok, msgs)


if __name__ == "__main__":
    unittest.main()
