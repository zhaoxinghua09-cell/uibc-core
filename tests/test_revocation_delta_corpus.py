"""The peer's shared delta-form vectors, read by this reader.

The 52 cases live in their sibling package (``probity-records``,
``vectors/shared/revocation.json``), not in the vectors repository and not here:
a corpus copied into our tree would stop being theirs. Set
``UIBC_REVOCATION_DELTA_CORPUS`` to the file to run this.

What is being checked is not "our reader runs" but "our reader and their answer
key agree member by member": seven acceptances on the whole folded state
(head, issue time, list id, the eight revoked sets, roots, sequence), and
forty-five refusals on the token and the position. A reader that refused
everything would score 45/52, and one that accepted everything 7/52; only
agreement on both halves is 52/52.
"""

from __future__ import annotations

import os

import pytest

from uibc_core import revocation_delta as rd

CORPUS = os.environ.get("UIBC_REVOCATION_DELTA_CORPUS")

needs_corpus = pytest.mark.skipif(
    not CORPUS or not os.path.isfile(CORPUS or ""),
    reason="set UIBC_REVOCATION_DELTA_CORPUS to the shared vectors file to read it",
)

#: The refusals the file expects, by token, at the head we measured.
_EXPECTED_REFUSALS = {
    "revocation_list_shape": 24,
    "revocation_list_signer_not_a_root": 6,
    "revocation_list_signature_unverified": 4,
    "revocation_entry_repeated": 3,
    "revocation_list_gap": 2,
    "revocation_list_rollback": 2,
    "revocation_entry_from_future": 1,
    "revocation_list_other_chain": 1,
    "revocation_list_previous_mismatch": 1,
    "revocation_list_time_reversed": 1,
}


@needs_corpus
def test_every_member_matches_the_answer_key():
    summary = rd.judge_suite(CORPUS)
    wrong = [(r["id"], r["mismatched"]) for r in summary["records"] if not r["conforms"]]
    assert wrong == []
    assert summary["members"] == summary["conforming"] == 52


@needs_corpus
def test_the_suite_keeps_the_shape_we_measured():
    cases = rd.load_suite(CORPUS)
    assert [c["id"] for c in cases] == ["RL%02d" % n for n in range(1, 53)]
    accept = [c for c in cases if c["expected"].get("state") is not None]
    refused = [c for c in cases if c["expected"].get("refused")]
    assert len(accept) == 7 and len(refused) == 45
    counts = {}
    for c in refused:
        counts[c["expected"]["refused"]] = counts.get(c["expected"]["refused"], 0) + 1
    assert counts == _EXPECTED_REFUSALS
    assert set(counts) <= set(rd.CODES)


@needs_corpus
def test_every_acceptance_carries_the_eight_sets_and_a_head():
    for case in rd.load_suite(CORPUS):
        state = case["expected"].get("state")
        if state is None:
            continue
        assert list(state["revoked"]) == list(rd.KINDS)
        assert state["head"].startswith("sha256:") and len(state["head"]) == 71
        assert isinstance(state["seq"], int) and state["seq"] >= 1


@needs_corpus
def test_a_signature_in_non_canonical_base64_is_unverified_not_malformed():
    """RL25: the one case our first pass read under the wrong token.

    A signature that is not the canonical base64 of 64 bytes is an
    *unverified* signature, not a malformed list: getting this wrong would tell
    a caller their document is invalid when the only thing wrong is its
    spelling of the signature.
    """
    cases = {c["id"]: c for c in rd.load_suite(CORPUS)}
    got = rd.judge_case(cases["RL25"])
    assert got["decision"] == "reject"
    assert got["refusal"]["code"] == "revocation_list_signature_unverified"
    assert got["refusal"]["detail"] == "signature_not_canonical_base64"


@needs_corpus
def test_a_root_rotation_inside_the_suite_is_folded_not_merely_accepted():
    """A case that revokes a root with a successor must show the successor as
    a root afterwards; accepting it without folding the rotation would pass an
    exit-code check and fail the next list."""
    cases = rd.load_suite(CORPUS)
    rotated = [c for c in cases
               if c["expected"].get("state") is not None
               and c["expected"]["state"]["roots"]
               and set(c["expected"]["state"]["roots"]) != set(c["roots"])]
    assert rotated, "the suite is expected to carry at least one rotated root set"
    for case in rotated:
        got = rd.judge_case(case)
        assert got["decision"] == "accept"
        assert got["state"]["roots"] == case["expected"]["state"]["roots"]
