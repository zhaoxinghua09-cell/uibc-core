"""The second implementation's answer on the competitor's inclusion vectors."""

import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, os.path.join(REPO, "tools", "third_party"))

import crosscheck_competitor_inclusion_sigstore as x  # noqa: E402


def _receipt():
    if not os.path.exists(x.RECEIPT):
        pytest.skip("receipt not built in this checkout")
    with open(x.RECEIPT, encoding="utf-8") as f:
        return json.load(f)


def test_the_receipt_agrees_with_the_published_verdicts():
    r = _receipt()
    t = r["totals"]
    assert t["inclusion_vectors"] == 37
    assert t["compared"] == 36
    assert t["agree_with_published"] == t["compared"]
    assert t["disagree_with_sweep"] == 0


def test_the_uncompared_vector_is_named_and_not_counted_as_agreement():
    r = _receipt()
    skipped = [v for v in r["vectors"] if v["library_verdict"] is None]
    assert len(skipped) == r["totals"]["skipped_no_empty_root"] == 1
    assert skipped[0]["library_status"] == "no-empty-root"
    assert all(v["agrees_with_published"] is not None
               for v in r["vectors"] if v["library_verdict"])


def test_the_receipt_describes_the_same_bytes_as_the_sweep():
    r = _receipt()
    sweep_receipt = os.path.join(REPO, "docs", "upstream-package",
                                 "competitor-defects", "corpus-sweep-39daf704.json")
    with open(sweep_receipt, encoding="utf-8") as f:
        sr = json.load(f)
    assert r["manifest_digest"] == x._digest(sr)
    assert r["corpus"].endswith(sr.get("head", "39daf704"))


def test_scope_stays_inclusion_only():
    """Consistency and canonical must not be folded into this count."""
    r = _receipt()
    assert r["covers"].startswith("inclusion only")
    families = {v["file"].split("-")[0] for v in r["vectors"]}
    assert families == {"INC"}


def test_a_wrong_root_is_refused_by_the_library(tmp_path):
    """A fold that cannot reach the root must come back as reject, not as a crash."""
    leaf = b"one leaf"
    inner, border = x.sig._decomp_inclusion_proof(0, 2)
    hashes = [bytes([0x33]) * 32] * (inner + border)
    mid = x.sig._chain_inner(x.sig._hash_leaf(leaf), hashes[:inner], 0)
    root = x.sig._chain_border_right(mid, hashes[inner:]).hex()
    vector = {"tree_size": 2, "index": 0, "record_hex": leaf.hex(),
              "proof": [h.hex() for h in hashes], "root": root}
    status, _ = x._library_fold(vector)
    assert status == "valid"
    status, _ = x._library_fold(dict(vector, root="ab" * 32))
    assert status == "invalid"
