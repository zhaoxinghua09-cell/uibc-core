"""The BID address rule, checked against the official SDK's own output.

Why this exists: our `_check_bid` reads the first two characters as
crypto/encoding and validates the ABNF. That is a *reading* of the protocol. The
stronger claim - "the address our code expects is the address the official SDK
produces for the same key" - needs an independent witness, and the witness is
`fixtures/bid/sdk_address.json`, printed by `tools/bid_sdk_address.mjs` from
`bid-sdk-nodejs` 1.0.1 (Caict).

The rule the SDK implements (`lib/keypair/index.js::_createAddress`):
    address = base58( sha256(rawPublicKey)[10:] ) prefixed with `did:bid:ef`
so a third party can re-derive it without either our code or the SDK.
"""

import hashlib
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from uibc_core import bid_protocol as B  # noqa: E402
from uibc_core import did_cn  # noqa: E402

RECORD = json.loads((REPO / "fixtures" / "bid" / "sdk_address.json").read_text(encoding="utf-8"))


def _raw_public_key():
    """The 32-byte key inside the SDK's `encPublicKey` (the BIF prefix dropped)."""
    return B.strip_key_prefix(RECORD["encPublicKey"])[0]


def test_our_rule_reproduces_the_address_the_official_sdk_printed():
    raw = _raw_public_key()
    derived = "did:bid:ef" + B.base58_encode(hashlib.sha256(raw).digest()[10:])
    assert derived == RECORD["address"], (
        "protocol rule and official SDK disagree: %s vs %s" % (derived, RECORD["address"]))


def test_the_address_we_recorded_satisfies_our_abnf_check():
    details = did_cn._check_bid(RECORD["address"].split("did:bid:", 1)[1])
    assert details["shape"] == "main"
    assert details["crypto"] == "Ed25519"
    assert details["encoding"] == "base58"
    assert details["suffix"] == RECORD["address"].split(":", 2)[-1]


def test_the_sdk_public_key_is_the_one_our_signed_fixture_uses():
    """Both fixtures come from the same seed, so they must name the same key."""
    signed = json.loads((REPO / "fixtures" / "bid" / "signed_document.json").read_text(encoding="utf-8"))
    assert signed["publicKey"][0]["publicKeyHex"] == RECORD["encPublicKey"]


def test_suffix_length_is_inside_the_protocol_range():
    suffix = RECORD["address"].split(":", 2)[-1]
    assert 22 <= len(suffix) <= 42, "protocol: suffix = (22,42)(ALPHA/DIGIT)"
