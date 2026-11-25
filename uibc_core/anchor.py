"""Anchor event resolution (S15).

A checkpoint head says "this is where my log was". An anchor says "and here is
evidence that somebody outside my log saw it at time T". The AER-1 corpus has
six anchored classes and, until now, we had no counterpart for any of them:

    anchored-valid                 -> resolves
    anchored-missing-proof         -> no inclusion proof
    anchored-bad-leaf-hash         -> leaf hash is not a digest
    anchored-bad-timestamp         -> anchored_at is not a legal time
    anchored-bad-id-version        -> anchor id/version malformed
    anchored-unresolvable-anchor   -> the declared root is not one we can recompute

The honest boundary: resolving against OUR OWN evidence Merkle root proves the
anchor was built from this package. It does NOT prove a third party saw it. An
anchor that names an external log is recorded as `external_unresolved` rather
than being counted as resolved - we will not turn "I could not check" into
"checked".

Layout inside a package (`evidence/anchors.json`):

    {"resolver": "evidence-merkle", "anchors": [
       {"id": "anchor-001", "version": 1,
        "leaf_hash": "<64 lowercase hex>",
        "anchored_at": "2026-11-17T08:00:00Z",
        "root": "<64 lowercase hex>", "size": 3, "index": 1,
        "proof": ["<hex>", "..."]}]}
"""

import re

from . import merkle

HEX64 = re.compile(r"^[0-9a-f]{64}$")
TS = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})$")

SUPPORTED_RESOLVERS = ("evidence-merkle",)


def _calendar_ok(y, m, d):
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return False
    days = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return d <= days[m - 1]


def _timestamp_ok(value):
    if not isinstance(value, str):
        return "anchored_at is not a string"
    m = TS.match(value)
    if not m:
        return "anchored_at is not RFC 3339 with a zone"
    if not _calendar_ok(int(m.group(1)), int(m.group(2)), int(m.group(3))):
        return "anchored_at is not a real calendar date"
    if int(m.group(6)) > 59:
        return "anchored_at carries a leap second"
    off = m.group(8)
    if off != "Z":
        hh, mm = int(off[1:3]), int(off[4:6])
        if hh > 14 or mm > 59:
            return "anchored_at has an out-of-range UTC offset"
    return None


def resolve(anchor, root=None, size=None, leaves=None):
    """Return (resolved: bool, problems: list). Never raises on hostile input."""
    problems = []
    if not isinstance(anchor, dict):
        return False, ["anchor is not an object"]

    aid = anchor.get("id")
    if not isinstance(aid, str) or not aid.strip():
        problems.append("anchor id is missing or empty")
    ver = anchor.get("version")
    if not isinstance(ver, int) or ver < 1:
        problems.append("anchor version must be an integer >= 1")

    leaf = anchor.get("leaf_hash")
    if not isinstance(leaf, str) or not HEX64.match(leaf):
        problems.append("leaf_hash is not 64 lowercase hex characters")

    ts = _timestamp_ok(anchor.get("anchored_at"))
    if ts:
        problems.append(ts)

    declared_root = anchor.get("root")
    if not isinstance(declared_root, str) or not HEX64.match(declared_root):
        problems.append("root is not 64 lowercase hex characters")
    idx, sz = anchor.get("index"), anchor.get("size")
    if not isinstance(idx, int) or isinstance(idx, bool):
        problems.append("index is not an integer")
    if not isinstance(sz, int) or isinstance(sz, bool) or sz < 1:
        problems.append("size is not a positive integer")
    proof = anchor.get("proof")
    if not isinstance(proof, list) or not proof:
        problems.append("proof is missing or empty")
    elif isinstance(sz, int) and sz > 1 and len(proof) == 0:
        problems.append("proof is empty for a multi-leaf tree")

    # resolvability: the declared root must be one we can recompute ourselves
    if root is not None and isinstance(declared_root, str):
        if declared_root != (root.hex() if isinstance(root, (bytes, bytearray)) else root):
            problems.append("declared root is not the root this package resolves to")
    if leaves is not None and isinstance(idx, int) and not (0 <= idx < len(leaves)):
        problems.append("anchor index is outside the evidence set")
    if leaves is not None and isinstance(idx, int) and 0 <= idx < len(leaves):
        # the claimed leaf must be the leaf that actually sits at that index;
        # otherwise the proof is being checked against a leaf the set does not
        # contain at that position - the classic "right proof, wrong subject".
        if isinstance(leaf, str) and leaf != leaves[idx].hex():
            problems.append("leaf_hash does not match the evidence leaf at that index")

    if problems:
        return False, problems

    try:
        siblings = [bytes.fromhex(h) for h in proof]
    except (TypeError, ValueError):
        return False, ["proof contains a non-hex sibling"]
    leaf_bytes = bytes.fromhex(leaf)
    try:
        root_bytes = bytes.fromhex(declared_root)
    except ValueError:
        return False, ["root is not valid hex"]
    if not merkle.verify_inclusion(leaf_bytes, idx, sz, siblings, root_bytes):
        return False, ["inclusion proof does not verify against the declared root"]
    return True, []


def check_document(doc, root=None, leaves=None):
    """Validate an anchors.json document. Returns (problems, resolved_count, external_count)."""
    problems = []
    if not isinstance(doc, dict):
        return ["anchors.json is not an object"], 0, 0
    resolver = doc.get("resolver")
    if resolver not in SUPPORTED_RESOLVERS:
        problems.append("UNSUPPORTED: resolver %r is not one we can resolve offline "
                        "(supported: %s)" % (resolver, ", ".join(SUPPORTED_RESOLVERS)))
        return problems, 0, 0
    anchors = doc.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        return ["anchors list is missing or empty"], 0, 0
    resolved = 0
    for i, a in enumerate(anchors):
        ok, probs = resolve(a, root=root, leaves=leaves)
        if ok:
            resolved += 1
        else:
            problems.append("anchor[%d] %s: %s" % (i, (a or {}).get("id", "?"), "; ".join(probs)))
    return problems, resolved, 0
