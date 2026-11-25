"""The ledger receipt must be internally consistent and reproducible."""

import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))

import build_upstream_ledger as ledger  # noqa: E402


def _receipt():
    if not os.path.exists(ledger.RECEIPT):
        pytest.skip("ledger receipt not built in this checkout")
    with open(ledger.RECEIPT, encoding="utf-8") as f:
        return json.load(f)


def test_receipt_covers_every_vector_once():
    r = _receipt()
    paths = [v["path"] for v in r["vectors"]]
    assert len(paths) == len(set(paths)) == r["manifest"]["count"] == 171
    assert r["totals"]["vectors"] == 171


def test_reach_levels_sum_to_the_total_and_match_the_families():
    r = _receipt()
    assert sum(r["totals"][k] for k in ledger.REACH) == r["totals"]["vectors"]
    for fam in r["families"].values():
        assert sum(fam[k] for k in ledger.REACH) == fam["vectors"]
        assert fam["signature_verified"] <= fam["vectors"]
    assert sum(f["vectors"] for f in r["families"].values()) == r["totals"]["vectors"]


def test_every_row_is_consistent_with_its_own_fields():
    """No row may claim a level its two layer columns do not support."""
    r = _receipt()
    for row in r["vectors"]:
        assert row["reach"] == ledger._reach(row["arith"], row["signature"])
        assert row["reach"] in ledger.REACH
        if row["reach"] == "verdict":
            assert row["arith"] != "none"
        if row["reach"] == "signature-only":
            assert row["signature"] == "verified"


def test_no_family_claims_a_count_it_does_not_have():
    """The published numbers of the sweep and the ledger cannot disagree."""
    r = _receipt()
    sweep_receipt = os.path.join(REPO, "docs", "upstream-package",
                                 "competitor-defects", "corpus-sweep-39daf704.json")
    sr = json.load(open(sweep_receipt, encoding="utf-8"))
    assert r["totals"]["verdict"] == sr["totals"]["n_replayable"]
    assert r["manifest"]["count"] == sr["manifest"]["count"]
    # Same bytes: the ledger's manifest digest is recomputed from the sweep receipt's
    # own file list, so a mismatch would mean the two receipts describe two corpora.
    assert r["manifest"]["digest"] == ledger._manifest_digest(sr["manifest"])
    assert r["totals"]["vectors"] == sr["totals"]["vectors"]


def test_a_flipped_signature_drops_the_vector_to_nothing(tmp_path):
    """The layer that says "verified" must be able to say "failed"."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    import jcs

    priv = Ed25519PrivateKey.generate()
    pk = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    body = {"alg": "EdDSA", "verdict": "accept"}
    sig = priv.sign(jcs.canonicalise(body).encode("utf-8")).hex()
    corpus = tmp_path / "corpus"
    (corpus / "token").mkdir(parents=True)
    (corpus / "token" / "good.json").write_text(json.dumps(
        {"id": "good", "public_key": pk,
         "text": json.dumps(dict(body, signature=sig)),
         "expect": {"result": "accept"}}), encoding="utf-8")
    flipped = ("%02x" % (int(sig[:2], 16) ^ 1)) + sig[2:]
    (corpus / "token" / "bad.json").write_text(json.dumps(
        {"id": "bad", "public_key": pk,
         "text": json.dumps(dict(body, signature=flipped)),
         "expect": {"result": "accept"}}), encoding="utf-8")

    built = ledger.build(str(corpus))
    by_id = {v["id"]: v for v in built["vectors"]}
    assert by_id["good"]["reach"] == "signature-only"
    assert by_id["bad"]["reach"] == "nothing"
    assert by_id["bad"]["signature"] == "failed"
