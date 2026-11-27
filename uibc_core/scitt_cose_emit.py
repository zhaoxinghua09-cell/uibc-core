#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Produce `aee-scitt-cose/v0.1` transparent statements, not just read them.

Why this exists
---------------
Reading somebody's corpus is half of an interop. The other half is producing
statements that conform to the same profile, so the other side's reader has
something of ours to judge. Until this module existed, `uibc_core/scitt_cose.py`
could take their vectors apart and say what was wrong with each one, and could
not hand back a single statement of its own.

What it emits, and what it deliberately does not
------------------------------------------------
It emits the wire form the profile describes: a tag-18 COSE_Sign1 whose
protected header carries alg (-19), kid, the CWT Claims once, the content type,
and - when the caller supplies one - the observer position at -70001, which is
then also named in `crit`. Receipts go where the profile puts them: a list of
tag-18 COSE_Sign1 messages under label 394 in the *unprotected* header, each
carrying vds (395), an inclusion proof (396 / -1) and a signature over the
root that its own proof yields for this entry.

It does not sign with nosec keys, does not invent claim values, and does not
silently drop a field it cannot place: an argument this profile has no room for
raises instead of being approximated. The deposit's own reader is the judge -
`tools/emit_and_check.py` builds a small corpus, then runs
`verify_transparent_statement` over it and reports each line, so "we produce
statements" is a claim with a receipt rather than an assertion.

Determinism
-----------
Same inputs, same bytes: the CBOR encoder here sorts map keys by encoded length
then bytewise (RFC 8949 4.2.1), strings are UTF-8, and nothing carries a
timestamp that was not passed in. That property is what lets a produced
statement be pinned by digest.
"""

from __future__ import annotations

import hashlib
import json

from . import cose_min, ed25519
from .cose_min import CborError
from .scitt_cose import (
    ALG_ED25519,
    CONTENT_TYPE,
    CWT_EXP,
    CWT_ISS,
    CWT_NBF,
    CWT_SUB,
    LBL_ALG,
    LBL_CONTENT_TYPE,
    LBL_CRIT,
    LBL_CWT_CLAIMS,
    LBL_KID,
    LBL_OBSERVER_POSITION,
    LBL_RECEIPTS,
    LBL_TYP,
    LBL_VDP,
    LBL_VDS,
    PROFILE,
    PROOF_INCLUSION,
    TYP,
    VDS_RFC9162_SHA256,
    leaf_hash,
    node_hash,
    sign1_from_bytes,
)

TAG_18 = b"\xd2"
PROFILE_NAME = PROFILE


class EmitError(ValueError):
    """Raised when a requested statement cannot be expressed in this profile."""


def _frame(array) -> bytes:
    """A COSE_Sign1 array wrapped in the tag the profile requires."""
    if not isinstance(array, (list, tuple)) or len(array) != 4:
        raise EmitError("a COSE_Sign1 is a four-element array")
    return TAG_18 + cose_min.encode(list(array))


def _sig_structure(protected: bytes, payload: bytes) -> bytes:
    # RFC 9052 4.4: ["Signature1", body_protected, external_aad, payload]; the
    # profile fixes external_aad to the empty bstr.
    return cose_min.encode(["Signature1", protected, b"", payload])


# --------------------------------------------------------------------------
# payloads
# --------------------------------------------------------------------------

def subject_digest(payload: bytes) -> str:
    """`sha256:<hex>` of the payload bytes - the value `sub` is bound to."""
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_payload(*, subject_sha256: str, profile: str = PROFILE_NAME,
                  issued_at: int | None = None, note: str | None = None) -> bytes:
    """A statement payload: a JSON object whose subject carries a sha256 digest.

    The field layout is the one `uibc_core/scitt_cose.py` reads for `sub`
    (`subject[0].digest.sha256`); anything else the profile does not pin, so it
    stays minimal and sorted for byte stability.
    """
    digest = subject_sha256.lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise EmitError("subject_sha256 must be 64 lowercase hex characters")
    body = {
        "digestAlgorithm": "sha256",
        "profile": profile,
        "subject": [{"digest": {"sha256": digest}}],
    }
    if issued_at is not None:
        body["issuedAt"] = int(issued_at)
    if note is not None:
        body["note"] = note
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


# --------------------------------------------------------------------------
# statements
# --------------------------------------------------------------------------

def declared_subject(payload: bytes) -> str:
    """The `sha256:<hex>` a payload's own subject carries.

    `sub` is a claim *about* the payload's subject, so it has to equal what the
    payload itself declares. Computing it from the payload bytes instead would
    produce a statement that its own reader refuses - which is how this was
    first written, and the reader was right to refuse it.
    """
    try:
        body = json.loads(payload.decode("utf-8"))
        digest = body["subject"][0]["digest"]["sha256"]
    except (UnicodeDecodeError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise EmitError("payload declares no subject digest: %s" % exc)
    return "sha256:" + str(digest).lower()


def build_statement(*, seed: bytes, kid: bytes, iss: str, payload: bytes,
                     sub: str | None = None,
                     exp: int | None = None, nbf: int | None = None,
                     observer: dict | None = None,
                     receipts: list[bytes] | None = None,
                     detached: bool = False,
                     content_type: str = CONTENT_TYPE,
                     typ: str = TYP) -> bytes:
    """One tag-18 COSE_Sign1 statement, signed by `seed`.

    `kid` is the raw bytes a relying party resolves against
    `trust.issuers[].kid` (hex there, bytes here). `observer`, when given, must
    be a map whose presence is declared in `crit` - a position that is present
    and not critical is exactly the defect the reader reports as
    `observer-position-not-critical`, so refusing to build it is the only
    honest option.
    """
    if not isinstance(seed, bytes) or len(seed) != 32:
        raise EmitError("seed must be 32 bytes")
    if not isinstance(kid, bytes) or not kid:
        raise EmitError("kid must be non-empty bytes")
    want_sub = declared_subject(payload)
    if sub is None:
        sub = want_sub
    if sub != want_sub:
        raise EmitError("sub %r does not match the digest the payload declares (%r)"
                        % (sub, want_sub))
    claims = {CWT_ISS: iss, CWT_SUB: sub}
    if exp is not None:
        claims[CWT_EXP] = int(exp)
    if nbf is not None:
        claims[CWT_NBF] = int(nbf)
    header = {
        LBL_ALG: ALG_ED25519,
        LBL_KID: kid,
        LBL_CWT_CLAIMS: claims,
        LBL_CONTENT_TYPE: content_type,
        LBL_TYP: typ,
    }
    if observer is not None:
        if not isinstance(observer, dict):
            raise EmitError("observer must be a map")
        header[LBL_OBSERVER_POSITION] = dict(observer)
        header[LBL_CRIT] = [LBL_OBSERVER_POSITION]
    protected = cose_min.encode(header)
    sig = ed25519.sign(seed, _sig_structure(protected, payload))
    uhdr = {}
    if receipts:
        uhdr[LBL_RECEIPTS] = [bytes(r) for r in receipts]
    payload_field = None if detached else payload
    return _frame((protected, uhdr, payload_field, sig))


def entry_bytes(statement_raw: bytes) -> bytes:
    """The registered entry: the statement with the receipts removed.

    Reuses the reader's own span-based reconstruction rather than re-encoding,
    so a produced statement and a read one cannot disagree about what was
    registered.
    """
    return sign1_from_bytes(statement_raw).entry_bytes()


# --------------------------------------------------------------------------
# Merkle tree and receipts (RFC 9162 2.1)
# --------------------------------------------------------------------------

def merkle_root(entries: list[bytes]) -> bytes:
    """MTH over registered entries (RFC 9162 2.1.1)."""
    if not entries:
        return hashlib.sha256(b"").digest()
    leaves = [leaf_hash(e) for e in entries]
    return _root_of(leaves)


def _root_of(leaves: list[bytes]) -> bytes:
    if len(leaves) == 1:
        return leaves[0]
    k = 1 << ((len(leaves) - 1).bit_length() - 1)
    return node_hash(_root_of(leaves[:k]), _root_of(leaves[k:]))


def inclusion_path(entries: list[bytes], index: int) -> list[bytes]:
    """The audit path for `index`, bottom-up, as RFC 9162 2.1.3.2 defines it."""
    if not 0 <= index < len(entries):
        raise EmitError("index %d outside a tree of %d" % (index, len(entries)))
    return _path([leaf_hash(e) for e in entries], index)


def _path(leaves: list[bytes], index: int) -> list[bytes]:
    if len(leaves) == 1:
        return []
    k = 1 << ((len(leaves) - 1).bit_length() - 1)
    if index < k:
        return _path(leaves[:k], index) + [_root_of(leaves[k:])]
    return _path(leaves[k:], index - k) + [_root_of(leaves[:k])]


def build_receipt(*, ts_seed: bytes, ts_kid: bytes, entry: bytes,
                  tree_size: int, leaf_index: int, path: list[bytes],
                  root: bytes) -> bytes:
    """One receipt: vds 1, an inclusion proof, and a signature over the root.

    The proof is stored the way the profile stores it - a single byte string
    under `-1` in the unprotected bucket (label 396), whose content is the
    CBOR array [tree_size, leaf_index, path]. The signature covers the root the
    proof yields for this entry, which is what makes a receipt issued about a
    different entry fail rather than pass.
    """
    if not isinstance(ts_seed, bytes) or len(ts_seed) != 32:
        raise EmitError("transparency-service seed must be 32 bytes")
    if not isinstance(root, bytes) or len(root) != 32:
        raise EmitError("root must be 32 bytes")
    if tree_size < 1 or leaf_index < 0 or leaf_index >= tree_size:
        raise EmitError("leaf_index %d is outside a tree of %d" % (leaf_index, tree_size))
    proof = cose_min.encode([int(tree_size), int(leaf_index),
                             [bytes(p) for p in path]])
    protected = cose_min.encode({LBL_ALG: ALG_ED25519, LBL_KID: bytes(ts_kid),
                                 LBL_VDS: VDS_RFC9162_SHA256})
    sig = ed25519.sign(ts_seed, _sig_structure(protected, root))
    return _frame((protected, {LBL_VDP: {PROOF_INCLUSION: [proof]}}, root, sig))


# --------------------------------------------------------------------------
# vectors, in the shape a corpus ships
# --------------------------------------------------------------------------

def build_vector(*, vector_id: str, statement: bytes, payload: bytes,
                 verification_time: int, issuer_iss: str, issuer_kid: bytes,
                 issuer_pub: bytes, ts_iss: str, ts_kid: bytes, ts_pub: bytes,
                 expected_verdict: str = "valid",
                 expected_codes: list[str] | None = None,
                 detached: bool = False) -> dict:
    """The JSON object a harness hands a foreign reader, trust inputs included."""
    return {
        "vector": vector_id,
        "profile": PROFILE_NAME,
        "transparentStatement": statement.hex(),
        "detachedPayload": payload.hex() if detached else None,
        "verificationTime": int(verification_time),
        "expected": {"verdict": expected_verdict,
                     "codes": sorted(expected_codes or [])},
        "trust": {
            "issuers": [{"iss": issuer_iss, "kid": issuer_kid.hex(),
                         "key": {"kty": "OKP", "crv": "Ed25519",
                                 "x": issuer_pub.hex()}}],
            "transparencyServices": [{"iss": ts_iss, "kid": ts_kid.hex(),
                                      "key": {"kty": "OKP", "crv": "Ed25519",
                                              "x": ts_pub.hex()}}],
        },
    }