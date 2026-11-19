"""The cross-check tool must keep working, and its note must stay honest.

The tool folds *another project's* committed vectors. It cannot depend on that
repository being cloned in CI, so these tests build a fixture with the same
shape (``leaf_entry`` = leaf input digest) and check that the tool adjudicates
it correctly: VALID must fold onto the stated root, a tampered path must not.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from uibc_core import merkle  # noqa: E402
import tools.crosscheck_scitt_cose_vectors as cc  # noqa: E402


def _make_vector(vid, size, index, tamper):
    inputs = [("leaf %d" % i).encode() for i in range(size)]
    leaves = [merkle.leaf_hash(x) for x in inputs]
    proof = list(merkle.audit_path(leaves, index))
    true_root = merkle.root_hash(leaves)
    if tamper:
        proof[0] = b"\x00" * 32
    return {
        "description": vid,
        "leaf_entry": inputs[index].hex(),   # leaf INPUT, as scitt-cose defines it
        "leaf_index": index,
        "tree_size": size,
        "inclusion_path": [h.hex() for h in proof],
        "reconstructed_root": true_root.hex(),
        "result": "INVALID_INCLUSION_PATH" if tamper else "VALID",
    }


class TestCrosscheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for vid, size, idx, tamper in (("valid-a", 8, 2, False),
                                       ("valid-b", 4, 0, False),
                                       ("fail-a", 8, 2, True)):
            d = os.path.join(self.tmp, "v1", vid)
            os.makedirs(d)
            with open(os.path.join(d, "expected.json"), "w", encoding="utf-8") as fh:
                json.dump(_make_vector(vid, size, idx, tamper), fh)

    def test_it_folds_valid_onto_the_root_and_tampered_away(self):
        rows, mismatches = cc.check(self.tmp)
        self.assertEqual(mismatches, 0, rows)
        by_id = {r[0]: r for r in rows}
        self.assertTrue(by_id["valid-a"][2])
        self.assertFalse(by_id["fail-a"][2])

    def test_cli_exits_zero_on_the_fixture(self):
        out = subprocess.run(
            [sys.executable, os.path.join(REPO, "tools", "crosscheck_scitt_cose_vectors.py"),
             "--dir", self.tmp],
            capture_output=True, text=True, cwd=REPO, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("mismatches: 0", out.stdout)


class TestTheNoteIsHonest(unittest.TestCase):
    def _note(self):
        with open(os.path.join(REPO, "docs", "external-review", "CROSSCHECK-SCITT-COSE.md"),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_it_says_what_it_is_not(self):
        doc = self._note()
        self.assertIn("not an audit of `scitt-cose`", doc.replace("**",""))
        self.assertIn("verifier agrees with theirs", doc.replace("**","").replace("\n"," "))

    def test_it_records_the_first_failed_run_as_ours(self):
        doc = self._note()
        self.assertIn("All five vectors disagreed", doc)
        self.assertIn("our reading error", doc)

    def test_it_does_not_claim_a_place_in_any_record(self):
        doc = self._note()
        self.assertIn("does not list this", doc)


if __name__ == "__main__":
    unittest.main()
