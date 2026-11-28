"""Canonical serialization + hashing (archive SS13).

RFC 8785 (JSON Canonicalization Scheme, JCS) compliant, effective v0.3.1.
Replaces the earlier PROVISIONAL sort_keys+compact JSON, which was byte-for-byte
identical to JCS for BMP-only keys/strings and integer numbers, but did not
guarantee UTF-16 code-unit key ordering for astral keys or ECMAScript number
serialization.

Why JCS (the highest-leverage "do it best" move): a UIBC artifact's hashes and
Ed25519 seal now re-derive with ANY standard JCS tool - W3C VC eddsa-jcs-2022
verifiers, SCITT-adjacent verifiers, the canonicalize npm package, etc. A
stranger verifies UIBC provenance with ZERO UIBC-specific code.

JCS rules implemented here:
  * Object keys sorted by UTF-16 code-unit order (recursive, into child objects
    and objects nested in arrays).
  * No insignificant whitespace between tokens.
  * Strings escaped per JSON: only " \\ and U+0000-U+001F (as \\b \\t \\n \\f \\r
    or \\uXXXX); / and non-ASCII are left literal UTF-8. This is exactly what
    json.dumps(s, ensure_ascii=False) produces.
  * Numbers serialized per ECMAScript Number::toString (RFC 8785 S 4.2.4):
    integers as digits; fractional / very large / very small use the shortest
    round-trip form (-0 -> 0). Non-finite (NaN/Infinity) are rejected because
    they are not valid JSON.
"""

import json
import math
import hashlib
from decimal import Decimal


def _es_double_str(x) -> str:
    """ECMAScript Number::toString for a finite non-integer-valued double.

    Two places where Python's own repr disagrees with ECMAScript, both of them
    silently correct-looking and both of them hash-changing:

      * exponent padding: repr(1e-07) == '1e-07', ECMAScript says '1e-7'
        (no leading zero in the exponent).
      * the fixed/exponent threshold: ECMAScript prints values with 1e-6 <= |x|
        < 1e21 in plain decimal form, so 1e-6 is '0.000001', not '1e-06'.

    A verifier holding a JCS implementation from another language compares
    bytes, so getting either of these wrong makes the same document hash two
    different ways across implementations. Found 2026-11-20 by comparing our
    Python path against our own JavaScript path (tools/verify-js): Python said
    '1e-07'/'1e-06' where JavaScript said '1e-7'/'0.000001'.
    """
    d = Decimal(repr(x))
    if 1e-6 <= abs(x) < 1e21:
        t = format(d, "f")
        if "." in t:
            t = t.rstrip("0").rstrip(".")
        return t
    t = format(d, "e")                      # e.g. '1E+21' / '1e-7'
    sep = "E" if "E" in t else "e"
    mant, _, exp = t.partition(sep)
    sign = exp[:1] if exp[:1] in "+-" else "+"
    digits = exp.lstrip("+-").lstrip("0") or "0"
    return mant.lower() + "e" + sign + digits


def _jcs_number_str(x) -> str:
    """ECMAScript Number::toString (RFC 8785 number rule)."""
    if isinstance(x, bool):
        raise TypeError("bool is not a JSON number")
    if isinstance(x, int):
        if -(2 ** 53) + 1 <= x <= 2 ** 53 - 1:
            return str(x)
        # An integer beyond the safe range is still an acceptable JSON number
        # when IEEE-754 can hold it exactly: `1e17` and `1e20` are exact doubles,
        # and ECMAScript serialises them in the fixed form this class of value
        # produces. Refusing them instead broke the canonical form's own
        # fixpoint - `canonicalize(1e20)` emits 21 digits, and re-reading those
        # digits yields an int that the old gate rejected, so the bytes the
        # library produced could not be canonicalised by the library. Atheris
        # found this on the first twenty-second run (2026-11-28).
        #
        # `2**53 + 1` is still refused, because no double equals it: the gate
        # is about precision loss in the counterparty's parser, not about size.
        try:
            as_double = float(x)
        except OverflowError:
            as_double = math.inf
        if as_double != x:
            raise ValueError(
                "JCS: integer %r outside ECMAScript safe range and not exactly "
                "representable as an IEEE-754 double" % (x,))
        return _jcs_number_str(as_double)
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            raise ValueError("JCS: NaN/Infinity are not valid JSON numbers")
        if x == 0.0:
            return "0"
        if x.is_integer():
            iv = int(x)
            if abs(iv) < 2 ** 53:
                return str(iv)
            if 1 <= len(str(abs(iv))) <= 21:
                return str(iv)          # ECMAScript keeps the fixed form up to 1e21
        return _es_double_str(x)
    raise TypeError("JCS: unsupported number type %r" % (type(x),))


def _jcs_scalar(v) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _jcs_number_str(v)
    if isinstance(v, str):
        # json.dumps(ensure_ascii=False) is a faithful JCS string serializer.
        return json.dumps(v, ensure_ascii=False)
    raise TypeError("JCS: unsupported scalar type %r" % (type(v),))


def _jcs_value(v) -> str:
    if isinstance(v, dict):
        parts = [json.dumps(k, ensure_ascii=False) + ":" + _jcs_value(v[k])
                 for k in sorted(v.keys(),
                                 key=lambda s: s.encode("utf-16-be"))]
        return "{" + ",".join(parts) + "}"
    if isinstance(v, list):
        return "[" + ",".join(_jcs_value(e) for e in v) + "]"
    return _jcs_scalar(v)


MAX_NESTING_DEPTH = 128


def nesting_depth(obj) -> int:
    """Deepest object/array nesting; a scalar is 0, `[]` is 1, `[[]]` is 2."""
    if isinstance(obj, dict):
        return 1 + max([nesting_depth(v) for v in obj.values()] or [0])
    if isinstance(obj, list):
        return 1 + max([nesting_depth(v) for v in obj] or [0])
    return 0


def check_nesting(obj, limit: int = MAX_NESTING_DEPTH) -> None:
    """Refuse a value nested deeper than `limit`.

    128 is the depth shared by the other implementations of this profile and
    stated in the draft's Conventions section; see
    docs/COMPETITIVE-COVERAGE-AAC.md. Refusing here keeps a document from
    reading one way in a shallow reader and another way in a deep one.
    """
    d = nesting_depth(obj)
    if d > limit:
        raise ValueError("nesting depth %d exceeds the limit of %d" % (d, limit))


def canonicalize(obj) -> bytes:
    """RFC 8785 (JCS) canonical serialization of a JSON-able object."""
    check_nesting(obj)
    return _jcs_value(obj).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_obj(obj) -> str:
    """SHA-256 over the RFC 8785 canonical serialization of a JSON-able object."""
    return sha256_hex(canonicalize(obj))


def hash_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def evidence_root(content_hashes: list) -> str:
    """Evidence Root v0.1: SHA-256 over the RFC 8785 canonical serialization of
    the sorted list of evidence content hashes.

    PROVISIONAL: not yet a Merkle tree. Upgrading to a proper Merkle/Hash Tree
    (archive SS13) requires the ratified canonical serialization first - which
    RFC 8785 now provides. The algorithm identifier is recorded in the
    verification report.
    """
    return sha256_hex(canonicalize(sorted(content_hashes)))


def evidence_root_merkle(content_hashes: list) -> str:
    """Evidence Root v0.2 (merkle-aer1-v1): Merkle root over content hashes.

    Leaves are ``merkle.leaf_hash(bytes.fromhex(content_hash))`` sorted by
    content hash, so the root is reproducible from the declared hashes alone
    and one item can be proven with ``log2(n)`` sibling hashes.
    """
    from .merkle import leaf_hash, root_hash
    leaves = [leaf_hash(bytes.fromhex(h)) for h in sorted(content_hashes)]
    return root_hash(leaves).hex()


def evidence_root_for(content_hashes: list, root_algorithm=None) -> str:
    """Dispatch on ``manifest["root_algorithm"]``; unknown/absent -> legacy v0.1."""
    alg = (root_algorithm or "").strip().lower()
    if alg.startswith("merkle-aer1"):
        return evidence_root_merkle(content_hashes)
    return evidence_root(content_hashes)


def index_metadata_digest(index: dict) -> str:
    """SHA-256 over the evidence-index METADATA only (v1.1, check S7).

    Scope is deliberate: content hashes are already covered twice (per-file
    hash in S4, combined root in S5), so binding them here would add nothing and
    would wrongly flag a harmless re-ordering of entries. What no check
    covered before was the metadata that tells a reader what an artifact IS:
    its path, its declared type, and its free-text note. A forged "reviewed and
    approved" note or a retyped evidence kind passed every hash check.

    Entries are sorted by path so the digest is order-independent, and
    "content_hash" is excluded on purpose.
    """
    meta = []
    for e in index.get("entries", []):
        meta.append({
            "path": str(e.get("path", "")),
            "type": e.get("type"),
            "note": e.get("note"),
            "action_digest": e.get("action_digest"),
        })
    meta.sort(key=lambda m: m["path"])
    return "sha256:" + sha256_hex(canonicalize(meta))


def lifecycle_head(events: list) -> str:
    """Head commitment over the lifecycle log (v1.1, checks S8/S9).

    Motivation: draft-bailey-scitt-agent-session-receipt carries an explicit
    head commitment because a hash chain on its own cannot see truncation -
    "the last N events are simply gone" leaves a shorter chain that is still
    internally valid. draft-maintainer-1f916-agent-record-01 makes the same
    point about checkpoints and adds that detecting a WHOLE-STORE ROLLBACK
    needs the head to be observed somewhere outside the store.

    So this computes a commitment to (count, last sequence number, digest of
    the last event) and the submitter seals it into the manifest. Two different
    guarantees follow, and they must not be confused:

      S8  head in manifest vs log on disk -> truncation / desync inside one
          package is caught even when the package is unsigned.
      S9  head pinned out-of-band (--expect-head, a log, a counterparty)
          -> substitution with an older but perfectly self-consistent package
          is caught. Without that out-of-band observation, a rollback is
          invisible, and no amount of hashing fixes it.
    """
    n = len(events)
    last = events[-1] if n else None
    return "sha256:" + sha256_hex(canonicalize({
        "count": n,
        "last_sequence_number": (last or {}).get("sequence_number"),
        "last_event_digest": (hash_obj(last) if last is not None else None),
    }))


def checkpoint_head(lifecyclehead: str, root: str, index_digest: str,
                    evidence_count: int) -> str:
    """One value that commits to the WHOLE package state (v1.1, S8/S9).

    The lifecycle-only head was not enough: adding evidence changes the evidence
    root but leaves the event log untouched, so a newer package and an older one
    shared the same lifecycle head. A checkpoint has to cover every axis a
    newer state can differ on, or pinning it detects nothing.
    """
    return "sha256:" + sha256_hex(canonicalize({
        "lifecycle_head": lifecyclehead,
        "evidence_root": root,
        "evidence_index_digest": index_digest,
        "evidence_count": evidence_count,
    }))
