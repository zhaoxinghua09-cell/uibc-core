"""The published proof was unreadable by the official client.

Measured 2026-11-20 on the release's own `CORPUS-DIGESTS.txt.ots`: `ots info` answered
"Error! 'cd.ots' is not a timestamp file", because the file was a bare serialized tree
without the DetachedTimestampFile header. Only this repository's tool could read it,
which is the opposite of a proof for strangers -- and it also meant `ots upgrade`,
the standard route to a Bitcoin block, could never be run on it by anyone.

These tests hold the container format, the digest binding, and the record that now
carries the block attestation.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ots_container as oc  # noqa: E402

ATT = os.path.join(ROOT, "anchors", "attestations", "v0.4.1")
DIGESTS = os.path.join(ATT, "CORPUS-DIGESTS.txt")
PROOF = os.path.join(ATT, "CORPUS-DIGESTS.txt.ots")
RECORD = os.path.join(ATT, "BITCOIN-ATTESTATION.json")

FROZEN_DIGEST = "153f9b898878aaa9da97c7a496dd22af124d9bb3112ec5fede0a04eff94df033"


def test_the_repository_proof_is_a_standard_container():
    blob = open(PROOF, "rb").read()
    assert oc.is_standard(blob), "the official ots client only reads files with the header"
    major, op_tag, digest = oc.header(blob)
    assert major == oc.MAJOR_VERSION
    assert op_tag == oc.OP_SHA256
    assert digest.hex() == FROZEN_DIGEST


def test_it_answers_for_the_committed_bytes():
    blob = open(PROOF, "rb").read()
    assert oc.binds(blob, oc.digest_of_file(DIGESTS))


def test_it_does_not_answer_for_other_bytes():
    blob = open(PROOF, "rb").read()
    other = bytes(range(32))
    assert not oc.binds(blob, other)


def test_a_bare_tree_cannot_be_bound_by_inspection():
    """This is the shape the release page publishes: 172 bytes, no header."""
    blob = open(PROOF, "rb").read()
    bare = blob[len(oc.MAGIC) + 2 + oc.DIGEST_LEN:]
    assert not oc.is_standard(bare)
    assert not oc.binds(bare, oc.digest_of_file(DIGESTS))
    assert oc.header(bare) is None


def test_wrapping_a_bare_tree_reproduces_the_standard_file():
    """Container only: the tree bytes are copied verbatim, so the evidence is the same."""
    blob = open(PROOF, "rb").read()
    bare = blob[len(oc.MAGIC) + 2 + oc.DIGEST_LEN:]
    digest = oc.digest_of_file(DIGESTS)
    assert oc.bare_to_standard(bare, digest) == blob


def test_wrapping_twice_is_refused():
    blob = open(PROOF, "rb").read()
    digest = oc.digest_of_file(DIGESTS)
    try:
        oc.bare_to_standard(blob, digest)
    except ValueError as exc:
        assert "already carries" in str(exc)
    else:
        raise AssertionError("a standard container must not be wrapped again")


def test_the_recorded_block_matches_the_proof_file_it_names():
    rec = json.load(io.open(RECORD, encoding="utf-8"))
    blob = open(os.path.join(ATT, rec["proof"]["file"]), "rb").read()
    assert rec["proof"]["bytes"] == len(blob)
    import hashlib
    assert rec["proof"]["sha256"] == hashlib.sha256(blob).hexdigest()
    assert rec["bitcoin"]["block_height"] == 976684
    assert rec["bitcoin"]["merkle_root"] == \
        "6fce2db8a60d50b8b927ba6f88edfebe2c030792b7d7afb21e95b19ce494adb4"
    assert rec["attests"]["sha256"] == FROZEN_DIGEST


def test_the_record_says_what_the_block_does_and_does_not_establish():
    rec = json.load(io.open(RECORD, encoding="utf-8"))
    claim = rec["what_it_establishes"]
    assert "does not say who published it" in claim
    assert "does not say the workflow behaved" in claim


def test_the_block_time_is_after_the_freeze():
    rec = json.load(io.open(RECORD, encoding="utf-8"))
    pin = json.load(io.open(os.path.join(ROOT, "anchors", "pins",
                                       "uibc-release-v0.4.1.json"), encoding="utf-8"))
    assert rec["bitcoin"]["block_time_utc"] > pin["frozen_at"]


def test_the_record_admits_what_it_does_not_check():
    rec = json.load(io.open(RECORD, encoding="utf-8"))
    assert "not walked" in rec["not_checked_here"] or "not walk" in rec["not_checked_here"]
