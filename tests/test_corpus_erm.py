"""Three attack families that came from an outside measuring tape.

ERM (Escape-Rate Matrix) hit this repo with 12 families on 2026-11-27. Three of
them had no counterpart in the 500-case corpus, and one of those three found a
real gap on the spot: S13 verified the Merkle proofs it was handed without
asking whether every leaf had one, so a package could delete two proofs and
still read as a complete tree.

Corpus: benchmarks/corpus/mutation-corpus-erm.json (15 cases).
Generator: tools/corpus_erm.py.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import outsider_audit as oa
from uibc_core.verify import verify

ERM = os.path.join(_REPO, "benchmarks", "corpus", "mutation-corpus-erm.json")
CLEAN = os.path.join(_REPO, "fixtures", "clean.uibc")


def check(report, cid):
    return next(c for c in report["checks"] if c["id"] == cid)


class TestErmCorpus(unittest.TestCase):
    def test_the_file_carries_every_family_it_claims(self):
        d = json.load(open(ERM, encoding="utf-8"))
        fams = d["families"]
        for name in ("seal-encoding", "merkle-double", "trunc-recompute",
                     "evidence-dotfile"):
            self.assertIn(name, fams)
        self.assertEqual(d["meta"]["cases"], 15)

    def test_no_case_in_the_committed_corpus_was_accepted(self):
        """Every case in this corpus is blocked, in both modes.

        If one starts passing, either the verifier regressed or the corpus entry
        no longer does what its description says - both are worth a red build.
        """
        d = json.load(open(ERM, encoding="utf-8"))
        bad = []
        for r in d["rows"]:
            for mode in ("open", "pinned"):
                if r.get("modes", {}).get(mode, {}).get("accepted"):
                    bad.append("%s/%s" % (r["id"], mode))
        self.assertEqual(bad, [], "accepted cases: %s" % bad)


class TestS13Coverage(unittest.TestCase):
    """The gap E2 found, pinned at the unit level."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_tree_that_drops_proofs_is_not_a_complete_tree(self):
        pkg = oa._prepare(CLEAN, self.tmp)
        oa.build_v11(pkg)                       # correct tree + proofs
        mp = os.path.join(pkg, "evidence", "merkle.json")
        doc = json.load(open(mp, encoding="utf-8"))
        self.assertEqual(check(verify(pkg), "S13")["result"], "PASS")
        doc["proofs"] = doc["proofs"][:-1]      # one leaf left unproven
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        r = check(verify(pkg), "S13")
        self.assertEqual(r["result"], "FAIL")
        self.assertIn("no inclusion proof", r["detail"])

    def test_the_full_tree_still_passes(self):
        pkg = oa._prepare(CLEAN, self.tmp)
        oa.build_v11(pkg)
        self.assertEqual(check(verify(pkg), "S13")["result"], "PASS")


if __name__ == "__main__":
    unittest.main()
