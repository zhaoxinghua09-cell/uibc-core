"""The v0.5.0 block record must agree with the proof next to it, offline.

Measured 2026-11-21: the page's own proof for v0.5.0 is a calendar attestation (272 bytes,
frozen). The block-level proof was produced later and stored in the repository, with a
record naming the block. A record and a proof that disagree are two documents, not one
claim -- so the record is compared with the proof by arithmetic here, in a test, and not
only by whoever happens to run the checker.
"""
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import ots_merkle  # noqa: E402

DIR = os.path.join(REPO, "anchors", "attestations", "v0.5.0")


def test_the_record_agrees_with_the_proof_it_cites():
    record = json.loads(io.open(os.path.join(DIR, "BITCOIN-ATTESTATION.json"),
                                encoding="utf-8").read())
    walked = ots_merkle.verify(os.path.join(DIR, "CORPUS-DIGESTS.txt.ots"),
                               os.path.join(DIR, "CORPUS-DIGESTS.txt"),
                               record["bitcoin"])
    assert walked["exit"] == 0, walked["lines"]
    assert walked["blocks"][0]["height"] == record["bitcoin"]["block_height"]
    assert walked["bound"], "the stored proof does not answer for the stored digest"


def test_the_record_says_the_page_keeps_its_own_proof():
    record = json.loads(io.open(os.path.join(DIR, "BITCOIN-ATTESTATION.json"),
                                encoding="utf-8").read())
    assert "frozen" in record["why_not_on_the_page"], (
        "the record must say why the page was not rewritten to carry the block proof")
    page = os.path.getsize(os.path.join(DIR, "CORPUS-DIGESTS.txt.ots"))
    assert page == record["proof"]["bytes"]
