"""What the official SDK's addresses prove - and what they do not.

History matters here. An earlier version of this file asserted "our rule
base58(sha256(pub)[10:]) reproduces the address the official SDK printed". It
passed - on the single sample we had. Asking the SDK for 50 deterministic keys
broke it: only 7 of 50 agreed. The coincidence had been mistaken for a law.

The SDK source (`bid-sdk-nodejs/lib/keypair/index.js::_createAddress`) does say
    address = "did:bid:ef" + sjcl.codec.base58.encode(sha256(rawPublicKey).slice(10))
with a byte-level slice, so the shape of the rule is what we read. But its base58
codec is not the Bitcoin-alphabet codec: decoding its output with a Bitcoin
decoder yields bytes that differ from sha256(pub)[10:]. So the address is
opaque to us, and we must not claim to re-derive it.

What does survive, over 50 samples instead of one: every address the official
implementation emits is accepted by our ABNF validator with the same
classification. That is the contract our resolver actually needs.
"""

import hashlib
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent

from uibc_core import bid_protocol as B  # noqa: E402  (path setup not needed: package is local)
from uibc_core import did_cn  # noqa: E402

BATCH = json.loads((REPO / "fixtures" / "bid" / "sdk_address_batch.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("row", BATCH, ids=[r["address"][-8:] for r in BATCH])
def test_every_sdk_address_is_accepted_by_our_abnf_validator(row):
    details = did_cn._check_bid(row["address"].split("did:bid:", 1)[1])
    assert details["shape"] == "main"
    assert details["crypto"] == "Ed25519"
    assert details["encoding"] == "base58"
    assert details["suffix"] == row["address"].split(":", 2)[-1]


def test_suffix_lengths_stay_inside_the_protocol_range():
    for row in BATCH:
        suffix = row["address"].split(":", 2)[-1]
        assert 22 <= len(suffix) <= 42, "protocol suffix is (22,42)(ALPHA/DIGIT), got %d" % len(suffix)


def test_the_batch_is_fifty_distinct_keys_and_addresses():
    assert len(BATCH) == 50
    assert len({r["encPublicKey"] for r in BATCH}) == 50
    assert len({r["address"] for r in BATCH}) == 50


def test_every_sdk_public_key_carries_the_three_byte_bif_prefix():
    for row in BATCH:
        raw, prefix = B.strip_key_prefix(row["encPublicKey"])
        assert prefix == "b06566", row["encPublicKey"][:8]
        assert len(raw) == 32


def test_bitcoin_base58_re_derivation_does_not_reproduce_the_sdk():
    """The open fact, stated as a fact rather than a comment.

    If this ever fails, the count moved: at 50 the SDK switched to a Bitcoin-compatible
    codec and the stronger re-derivation claim could be restored deliberately.
    """
    matches = 0
    for row in BATCH:
        raw, _ = B.strip_key_prefix(row["encPublicKey"])
        derived = "did:bid:ef" + B.base58_encode(hashlib.sha256(raw).digest()[10:])
        matches += derived == row["address"]
    assert matches == 7, (
        "expected 7/50 coincidental overlaps between the SDK's codec and Bitcoin base58; got %d/50 "
        "(%s)" % (matches, "revisit the re-derivation claim" if matches == 50 else "investigate"))


def test_signed_fixture_and_sdk_record_share_the_three_byte_prefix():
    signed = json.loads((REPO / "fixtures" / "bid" / "signed_document.json").read_text(encoding="utf-8"))
    assert signed["publicKey"][0]["publicKeyHex"].startswith("b06566")
