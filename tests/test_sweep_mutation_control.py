"""The mutation control has to keep failing in the direction it claims.

`sweep_competitor_corpus.py` reports zero contradictions. A negative result is
only worth reading if the instrument is known to be able to produce a positive,
so `tools/sweep_mutation_control.py` perturbs the real corpus and checks that the
sweep notices. These tests pin the three things that make that claim honest:

  * the instrument fires on every change that actually moves the arithmetic;
  * it does not fire on the one change arithmetic cannot see (a tree size that
    carries the same hashes), which is reported apart rather than counted as a
    success;
  * the numbers in the receipt and the numbers in the doc stay equal.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECEIPT = os.path.join(ROOT, "docs", "upstream-package", "competitor-defects",
                       "sweep-mutation-control.json")
DOC = os.path.join(ROOT, "docs", "COMPETITOR-CORPUS-SWEEP.md")
TOOL = os.path.join(ROOT, "tools", "sweep_mutation_control.py")


def _receipt():
    with open(RECEIPT, encoding="utf-8") as f:
        return json.load(f)


def test_the_tool_passes_its_own_selftest():
    out = subprocess.run([sys.executable, TOOL, "--selftest"],
                         capture_output=True, text=True, check=True)
    assert "13 families" in out.stdout
    assert "11 arithmetic checked" in out.stdout


def test_every_arithmetic_mutation_was_caught():
    t = _receipt()["totals"]
    assert t["applied"] == 196
    assert t["detected"] == 183
    assert t["ambiguous"] == 13
    assert t["unexplained"] == 0
    # The three buckets are the whole set: nothing may be silently dropped.
    assert t["detected"] + t["ambiguous"] + t["unexplained"] == t["applied"]


def test_nothing_the_detector_was_supposed_to_catch_was_missed():
    """A family that changes the arithmetic must have caught every instance."""
    r = _receipt()
    for group in r["families"]:
        for fam in group["families"]:
            if fam["expected_to_detect"]:
                assert fam["unexplained"] == 0, (group["kind"], fam["family"])
                assert fam["ambiguous"] == 0, (group["kind"], fam["family"])
                assert fam["detected"] == fam["applied"], (group["kind"], fam["family"])


def test_the_only_blind_spot_is_the_tree_size_and_it_is_listed_by_name():
    r = _receipt()
    assert len(r["ambiguous"]) == 13
    assert {m["mutation"] for m in r["ambiguous"]} == {"tree_size+1", "new_size+1"}
    assert len({m["id"] for m in r["ambiguous"]}) == 13
    # Every one of them was consistent before the mutation; that is what makes
    # the miss meaningful rather than a vector that was already broken.
    assert r["before"]["consistent"] == 69
    assert r["before"]["inconsistent"] == 0


def test_the_corpus_names_the_ambiguity_it_does_not_test():
    """One record/index/proof group appears at three tree sizes; the upstream
    vector's own note says a size-7 proof also folds at size 8."""
    a = _receipt()["ambiguity"]
    assert a["groups_with_two_sizes"] == 1
    assert a["ids"] == ["INC-N-root-altered", "INC-N-wrong-tree-size",
                        "INC-O-size-not-bound-by-root"]


def test_the_receipt_is_tied_to_the_swept_head():
    r = _receipt()
    assert r["head"] == "39daf704"
    assert "39daf704" in r["corpus"]
    assert r["before"]["vectors"] == 171
    assert r["before"]["replayable"] == 69


def test_the_doc_repeats_the_receipt_and_not_a_rounder_number():
    with open(DOC, encoding="utf-8") as f:
        doc = f.read()
    for needle in ("196", "183", "13", "ambiguous", "sweep-mutation-control.json",
                   "INC-O-size-not-bound-by-root"):
        assert needle in doc, needle
