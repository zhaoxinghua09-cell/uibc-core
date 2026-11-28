"""Pinning the address rule to bytes: 50 SDK samples, one standard example, one letter table.

The claim under test is narrow and falsifiable: a ``did:bid`` address is
``base58_<SDK alphabet>(sha256(raw_public_key)[10:])`` - 50 of 50 evidence - and
that the alphabet, not the hash, is what made an earlier round of this
repository report "derivable only 7 times in 50".
"""

import hashlib
import json
import os
import re

import pytest

from uibc_core import bid_address as A

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "fixtures", "bid", "sdk_address_batch.json")

# RFC-003 §5.1, its only worked example (private key and raw public key printed in the text).
RFC_PRIVATE = "privfBrqvDdhNK978UpDpCTtmCX5ymUE7Le2PS1uPxVcubdrM"
RFC_RAW_PUBLIC = "d308378e6b5ff0c2b4be3da741538004525d6388e5df32deb79e2b0c02f133c7"
RFC_ADDRESS = "did:bid:38VPR182Y4uTkq32fykXjbKBPdQZutH"


def _samples():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def test_the_alphabets_differ_in_exactly_four_case_swapped_letters():
    # Not "a different alphabet" vaguely: four positions, all case swaps of b/B and u/U.
    # That is why 7 of 50 addresses coincided under the Bitcoin alphabet - those seven
    # happened to contain none of these four letters. A big disclaimer becomes a
    # two-line transform any Base58 library can apply.
    diffs=[(i,u,v) for i,(u,v) in enumerate(zip(A.SDK_BASE58_ALPHABET,A.BITCOIN_BASE58_ALPHABET)) if u!=v]
    assert diffs==[(10,"b","B"),(27,"u","U"),(34,"B","b"),(52,"U","u")]
    assert A.BID_TO_BITCOIN_SWAPS=={"b":"B","B":"b","u":"U","U":"u"}
    assert len(A.SDK_BASE58_ALPHABET)==len(set(A.SDK_BASE58_ALPHABET))==58


def test_swapping_four_letters_turns_a_bid_suffix_into_bitcoin_base58():
    def b58_bitcoin(data):
        n=int.from_bytes(data,"big"); out=[]
        while n:
            n,rem=divmod(n,58); out.append(A.BITCOIN_BASE58_ALPHABET[rem])
        zeros=len(data)-len(data.lstrip(b"\x00"))
        return "1"*zeros+"".join(reversed(out))

    for sample in _samples():
        raw=A.strip_key_prefix(sample["encPublicKey"])
        bitcoin=b58_bitcoin(hashlib.sha256(raw).digest()[10:])
        bid_suffix=sample["address"].split(":")[-1][2:]
        assert A.bid_suffix_to_bitcoin(bid_suffix)==bitcoin
        assert A.bitcoin_to_bid_suffix(bitcoin)==bid_suffix


def test_all_fifty_official_addresses_are_re_derived_without_a_version_byte():
    mismatches = []
    for sample in _samples():
        derived = A.derive_did(sample["encPublicKey"], "Ed25519", version_byte=False)["did"]
        if derived != sample["address"]:
            mismatches.append((sample["address"], derived))
    assert mismatches == [], "%d/50 failed: %r" % (len(mismatches), mismatches[:3])


def test_the_same_fifty_fail_with_the_version_byte_so_the_variant_is_real():
    # If this ever passes 50/50 too, the two variants have collapsed and the
    # "the SDK drops RFC-003 step 3" note in the docs must be revisited.
    hits = sum(1 for s in _samples()
               if A.derive_did(s["encPublicKey"], "Ed25519", version_byte=True)["did"] == s["address"])
    assert hits == 0


def test_bitcoin_alphabet_reproduces_only_a_handful_of_the_fifty():
    # This is the number an earlier round reported as 7/50. Keep it as a red-if-changed
    # tripwire: it says "we know exactly how wrong the Bitcoin alphabet is".
    def b58_bitcoin(data):
        n = int.from_bytes(data, "big")
        out = []
        while n:
            n, rem = divmod(n, 58)
            out.append(A.BITCOIN_BASE58_ALPHABET[rem])
        zeros = len(data) - len(data.lstrip(b"\x00"))
        return "1" * zeros + "".join(reversed(out))

    hits = 0
    for sample in _samples():
        raw = A.strip_key_prefix(sample["encPublicKey"])
        suffix = sample["address"].split(":")[-1][2:]
        if b58_bitcoin(hashlib.sha256(raw).digest()[10:]) == suffix:
            hits += 1
    assert hits == 7


def test_rfc_003_worked_example_reproduces_exactly_with_the_version_byte():
    # The RFC prints `did:bid:38VPR...` - i.e. it omits the algorithm+coding letters
    # that its own §5.1 structure section requires and that every live address carries.
    # The 22-byte suffix is what the algorithm produces; that is what is pinned here.
    derived = A.derive_did("b0" + RFC_RAW_PUBLIC, "Ed25519", version_byte=True)
    assert derived["suffix"] == RFC_ADDRESS.split("did:bid:")[1]
    assert derived["version_byte"] == "0x01"
    # And the form the RFC prints is not a valid address: the two letters are missing.
    assert derived["did"] == "did:bid:ef" + derived["suffix"] != RFC_ADDRESS


def test_rfc_003_example_does_not_reproduce_without_the_version_byte():
    # Pins the divergence instead of describing it: the standard's own example
    # needs the byte that the shipped SDK later commented out.
    assert A.derive_did("b0" + RFC_RAW_PUBLIC, "Ed25519", version_byte=False)["did"] != RFC_ADDRESS


def test_round_trip_and_leading_zero_handling():
    payload = bytes.fromhex("c6fd8f46575a3b142f16691b522e07a3cb1d5c1a16da")
    encoded = A.b58encode(payload)
    assert A.b58decode(encoded) == payload
    # sjcl emits one LEADER ('1') per leading zero byte, not a single one.
    padded = b"\x00\x00" + payload
    assert A.b58encode(padded) == "11" + encoded
    assert A.b58decode("11" + encoded) == padded
    assert A.b58encode(b"") == ""


def test_foreign_characters_are_refused_not_silently_skipped():
    # '0' and 'O' and 'l' are excluded from every Base58 alphabet; a decoder that
    # ignores them would accept many misspelled addresses.
    for bad in ("0", "O", "l", "I"):
        with pytest.raises(ValueError):
            A.b58decode("abc" + bad)


def test_sm2_hashes_with_sm3_and_still_lands_in_the_abnf_range():
    raw = bytes(range(32)) * 2  # 64 bytes x||y
    derived = A.derive_did("b06566" + raw.hex(), "SM2")
    assert derived["algorithm"] == "SM2"
    assert derived["hash_hex"] == hashlib.new("sm3", raw).hexdigest()
    assert derived["did"].startswith("did:bid:zf")
    suffix = derived["suffix"]
    assert re.fullmatch(r"[A-Za-z0-9]+", suffix)
    assert 22 <= len(suffix) <= 42


def test_sub_chain_address_carries_the_ac_code_before_the_letters():
    main = A.derive_did("b0" + RFC_RAW_PUBLIC, version_byte=True)["did"]
    sub = A.derive_did("b0" + RFC_RAW_PUBLIC, acns="byo1", version_byte=True)["did"]
    assert main == "did:bid:ef38VPR182Y4uTkq32fykXjbKBPdQZutH"
    assert sub == "did:bid:byo1:" + main.split("did:bid:", 1)[1]
    with pytest.raises(ValueError):
        A.derive_did("b0" + RFC_RAW_PUBLIC, acns="toolong")


def test_address_matches_accepts_both_variants_but_not_a_wrong_key():
    assert A.address_matches("b0" + RFC_RAW_PUBLIC, "did:bid:ef" + RFC_ADDRESS.split("did:bid:")[1])
    # the letter-less form the RFC prints is not accepted: an address without its
    # algorithm/coding letters is not an address this resolver would parse
    assert A.address_matches("b0" + RFC_RAW_PUBLIC, RFC_ADDRESS) is False
    assert A.address_matches("b0" + RFC_RAW_PUBLIC,
                             A.derive_did("b0" + RFC_RAW_PUBLIC, version_byte=False)["did"])
    other = "b0" + "11" * 32
    assert A.address_matches(other, RFC_ADDRESS) is False


def test_unknown_algorithm_is_named_in_the_error():
    with pytest.raises(ValueError) as err:
        A.derive_did("b0" + RFC_RAW_PUBLIC, "RSA")
    assert "RSA" in str(err.value)
