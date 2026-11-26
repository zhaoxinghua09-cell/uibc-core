"""The signed head statement must be RFC 8785 canonical bytes, not "sorted json".

A second implementation re-deriving the signature needs the exact byte string.
Section 16 of the draft says RFC 8785 (JCS); if this file ever drifts from that
claim, the signature is unverifiable by anyone who reads the spec instead of the
code.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.canonical import canonicalize  # noqa: E402
from tools import cosign_head  # noqa: E402


def test_message_is_jcs_of_the_same_object():
    signed = cosign_head.message("ab" * 32, "owner", 7, "sha256:" + "cd" * 32)
    expected = canonicalize({
        "head": "ab" * 32,
        "role": "owner",
        "tree_size": 7,
        "vds": "sha256:" + "cd" * 32,
    })
    assert signed == expected


def test_member_order_does_not_change_the_bytes():
    a = cosign_head.message("ff" * 32, "witness", 12)
    b = canonicalize({"role": "witness", "tree_size": 12, "head": "ff" * 32})
    assert a == b


def test_absent_optional_members_are_absent_not_null():
    # tree_size/vds are omitted when unobserved, so a verifier cannot be told
    # "the signer saw null" and pass it off as "the signer saw nothing".
    signed = cosign_head.message("00" * 32, "owner", None, None)
    body = json.loads(signed.decode("utf-8"))
    assert body == {"head": "00" * 32, "role": "owner"}
