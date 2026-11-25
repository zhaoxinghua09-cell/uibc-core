"""Deriving a ``did:bid`` address from a public key - and the alphabet that hid it.

Why this module exists
----------------------
An earlier round of this repository concluded, in writing, that an official BID
address could be *checked* but not *re-derived*: 50 addresses produced by the
official SDK (``bid-sdk-nodejs`` 1.0.1) were run against the rule in
《星火·链网BID协议》 §5 (``base58(sha256(pub)[10:])``) and only **7 of 50** matched.
The working assumption was that the SDK's Base58 differed in some structural way
(byte chunking, extra prefix, a different hash).

It does not. The SDK uses an ordinary big-integer Base58 with a **different
alphabet** (``brdc-sjcl`` ``sjcl.codec.base58``, its source line reads
``alphabets:"123456789AbCDEFGHJKLMNPQRSTuVWXYZaBcdefghijkmnopqrstUvwxyz"``).
Digits 1-9 are identical, which is why 7 of 50 strings coincided - short
accidental agreements, not a rule. Substitute the alphabet and all **50 of 50**
match, byte for byte. See ``docs/ADDRESS-DERIVATION.md``.

So the honest statement is not "opaque, check only". It is:

    A BID address is fully derivable from the public key, given the alphabet
    the implementation actually uses - and the standard and the implementation
    do not agree on that alphabet, nor on whether a version byte is prepended.

That second clause is the interesting part, and the reason this module keeps the
version byte as an explicit switch instead of a default:

  * RFC-003 §5.1 (2021-12-07) specifies a one-byte version (``0x01``) in front of
    the 22 truncated hash bytes, and prints one worked example. That example
    reproduces **exactly** with ``version_byte=True`` and the SDK alphabet -
    ``did:bid:38VPR182Y4uTkq32fykXjbKBPdQZutH``.
  * The shipped SDK has that step commented out (``keypair/index.js`` lines 60-62:
    ``// const head = [0x1]`` / ``// mix = sjcl.bitArray.concat(head, mix)``) and
    emits 22-byte, version-free addresses. All 50 samples reproduce with
    ``version_byte=False``.

Both are byte-reproducible. They cannot both be "the" rule, so this module does
not pick one silently: the caller says which, and the difference is visible in
the return value.

What is *not* claimed here: that a derivation is authoritative for a given
network. A resolver must still accept any address its ABNF accepts; derivation is
a consistency check (does this document's address correspond to its key?), not an
admission rule.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Optional

# The alphabet used by brdc-sjcl (the Base58 codec the official SDK vendors).
# NOTE: this is NOT Bitcoin's alphabet - but the difference is exactly four
# case swaps of b/B and u/U, at positions 10, 27, 34 and 52. Equivalent statement:
# a BID suffix is Bitcoin Base58 with the case of those four letters flipped.
SDK_BASE58_ALPHABET = "123456789AbCDEFGHJKLMNPQRSTuVWXYZaBcdefghijkmnopqrstUvwxyz"
BITCOIN_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BID_TO_BITCOIN_SWAPS = {"b": "B", "B": "b", "u": "U", "U": "u"}

_ALPHABET_INDEX = {ch: i for i, ch in enumerate(SDK_BASE58_ALPHABET)}

# RFC-003 §5.1: one lowercase letter for the key algorithm.
ALGORITHM_LETTERS = {"Ed25519": "e", "SM2": "z", "Secp256k1": "s"}
# RFC-003 §5.1: one lowercase letter for the suffix encoding.
CODEC_LETTERS = {"base58": "f", "base64": "s", "bech32": "t"}

HASH_LEN = 22          # RFC-003 §5.1: truncate the digest to 22 bytes
VERSION_BYTE = 0x01    # RFC-003 §5.1 step 3; dropped by the shipped SDK

# BIF public keys arrive hex-encoded with an algorithm prefix of 1 or 3 bytes.
_KEY_PREFIXES = ("b06566", "b0")


def b58encode(data: bytes) -> str:
    """Base58 with the SDK alphabet, leading zero bytes encoded as '1'.

    Mirrors ``sjcl.codec.base58.encode``: big-integer conversion, then one
    literal ``LEADER`` character per leading zero byte.
    """
    if not data:
        return ""
    n = int.from_bytes(data, "big")
    out = []
    while n:
        n, rem = divmod(n, 58)
        out.append(SDK_BASE58_ALPHABET[rem])
    zeros = len(data) - len(data.lstrip(b"\x00"))
    return "1" * zeros + "".join(reversed(out))


def b58decode(text: str) -> bytes:
    """Inverse of :func:`b58encode`; raises ``ValueError`` on a foreign character."""
    if not text:
        return b""
    n = 0
    for ch in text:
        if ch not in _ALPHABET_INDEX:
            raise ValueError("not a BID Base58 character: %r" % ch)
        n = n * 58 + _ALPHABET_INDEX[ch]
    zeros = len(text) - len(text.lstrip("1"))
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * zeros + body


def bid_suffix_to_bitcoin(suffix: str) -> str:
    """Translate a BID suffix into Bitcoin Base58, so any Base58 library can read it."""
    return "".join(BID_TO_BITCOIN_SWAPS.get(ch, ch) for ch in suffix)


def bitcoin_to_bid_suffix(text: str) -> str:
    """Inverse of :func:`bid_suffix_to_bitcoin` (the swaps are their own inverse)."""
    return bid_suffix_to_bitcoin(text)


def strip_key_prefix(public_key_hex: str) -> bytes:
    """Raw key bytes from the BIF-prefixed hex form (``b06566`` / ``b0`` / bare)."""
    raw = public_key_hex.strip().lower()
    if raw.startswith("0x"):
        raw = raw[2:]
    for prefix in _KEY_PREFIXES:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    try:
        return bytes.fromhex(raw)
    except ValueError as exc:
        raise ValueError("publicKeyHex is not hex: %r" % public_key_hex) from exc


def digest_for(raw_public_key: bytes, algorithm: str) -> bytes:
    """RFC-003 §4.1.1 step 2: SM2 hashes with SM3, Ed25519/Secp256k1 with SHA-256."""
    algo = algorithm.strip()
    if algo.upper().replace("_", "-") in ("SM2", "SM-2"):
        return hashlib.new("sm3", raw_public_key).digest()
    return hashlib.sha256(raw_public_key).digest()


def address_suffix(raw_public_key: bytes, algorithm: str = "Ed25519",
                   version_byte: bool = False) -> str:
    """The Base58 suffix only (no ``did:bid:``, no algorithm/codec letters)."""
    digest = digest_for(raw_public_key, algorithm)
    # RFC-003 §5.1 step 2: take the *last* 22 bytes of the 32-byte digest.
    truncated = digest[len(digest) - HASH_LEN:]
    payload = (bytes([VERSION_BYTE]) + truncated) if version_byte else truncated
    return b58encode(payload)


def derive_did(public_key_hex: str, algorithm: str = "Ed25519",
               acns: Optional[str] = None, version_byte: bool = False) -> Dict[str, str]:
    """Full ``did:bid`` address for a public key, with every part exposed.

    Returns a dict rather than a bare string on purpose: with two live variants
    of the rule (RFC-003's version byte vs the SDK's omission), a string would
    hide which one was used.
    """
    raw = strip_key_prefix(public_key_hex)
    algo_letter = _letter(ALGORITHM_LETTERS, algorithm, "algorithm")
    suffix = address_suffix(raw, algorithm, version_byte)
    body = "%s%s%s" % (algo_letter, CODEC_LETTERS["base58"], suffix)
    if acns:
        if len(acns) != 4:
            raise ValueError("AC code is four characters, got %r" % acns)
        body = "%s:%s" % (acns, body)
    return {
        "did": "did:bid:" + body,
        "suffix": suffix,
        "algorithm": algorithm,
        "codec": "base58",
        "acns": acns or "",
        "version_byte": "0x%02x" % VERSION_BYTE if version_byte else "",
        "hash_hex": digest_for(raw, algorithm).hex(),
        "key_bytes": str(len(raw)),
    }


def _letter(table: Dict[str, str], name: str, kind: str) -> str:
    for key, value in table.items():
        if key.lower() == str(name).lower():
            return value
    raise ValueError("unsupported %s %r; known: %s" % (kind, name, ", ".join(sorted(table))))


def address_matches(public_key_hex: str, did: str, algorithm: str = "Ed25519",
                    acns: Optional[str] = None) -> bool:
    """Does a document's address correspond to its key? True for either variant.

    Deliberately tolerant: an address derived with the RFC-003 version byte and
    one without are both real (the standard says one, the SDK ships the other),
    so a mismatch report must be about the key, not about which variant the peer
    implemented.
    """
    for version_byte in (False, True):
        if derive_did(public_key_hex, algorithm, acns, version_byte)["did"] == did:
            return True
    return False
