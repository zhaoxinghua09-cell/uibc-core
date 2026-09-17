"""Canonical serialization + hashing (archive SS13).

PROVISIONAL implementation: JSON with sorted keys, no whitespace, UTF-8.
A future version MUST migrate to full RFC 8785 (JCS) compliance before any
signature/Merkle construction is ratified - JSON formatting differences would
otherwise break hash comparability (archive warning, SS13).
"""

import hashlib
import json


def canonicalize(obj) -> bytes:
    """Provisional canonical JSON encoding (sorted keys, compact, UTF-8)."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_obj(obj) -> str:
    """SHA-256 over the canonical serialization of a JSON-able object."""
    return sha256_hex(canonicalize(obj))


def hash_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def evidence_root(content_hashes: list) -> str:
    """Evidence Root v0.1: SHA-256 over the canonical serialization of the
    sorted list of evidence content hashes.

    PROVISIONAL: not yet a Merkle tree. Upgrading to a proper Merkle/Hash Tree
    (archive SS13) requires the ratified canonical serialization first. The
    algorithm identifier is recorded in the verification report.
    """
    return sha256_hex(canonicalize(sorted(content_hashes)))
