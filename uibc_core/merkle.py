"""Merkle inclusion proofs (RFC 6962 style), standard library only.

Why this exists: the AER-1 conformance corpus has a whole class we had nothing
for - `base/merkle-vectors.json`, 9 vectors / 12 checks. A hash chain answers
"was file N changed?"; a Merkle tree answers "is this one file inside a set of
size N that you committed to, without my handing you all N files?" Those are
different questions and only the second one scales to a device with thousands
of evidence objects.

Construction (RFC 6962, the Certificate Transparency tree):
    leaf hash  = SHA-256(0x00 || leaf_bytes)
    node hash  = SHA-256(0x01 || left || right)
    an unbalanced tail is promoted, not duplicated - duplicating it would make
    two different trees share a root, which is the classic mistake.

Proofs are index-addressed, so a verifier needs: the leaf, its index, the tree
size, the sibling path, and the root it was told out of band.
"""

import hashlib

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(data: bytes) -> bytes:
    return _sha256(LEAF_PREFIX + data)


def node_hash(left: bytes, right: bytes) -> bytes:
    return _sha256(NODE_PREFIX + left + right)


def _largest_pow2_below(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def root_hash(leaves):
    """Merkle root over already-hashed leaves. Empty tree -> all-zero digest."""
    leaves = list(leaves)
    if not leaves:
        return b"\x00" * 32
    if len(leaves) == 1:
        return leaves[0]
    k = _largest_pow2_below(len(leaves))
    return node_hash(root_hash(leaves[:k]), root_hash(leaves[k:]))


def root_from_data(items) -> str:
    return root_hash([leaf_hash(i) for i in items]).hex()


def audit_path(leaves, index):
    """Sibling hashes from the leaf up to the root (RFC 6962 PATH)."""
    leaves = list(leaves)
    if not 0 <= index < len(leaves):
        raise IndexError("leaf index out of range")
    if len(leaves) == 1:
        return []
    k = _largest_pow2_below(len(leaves))
    if index < k:
        return audit_path(leaves[:k], index) + [root_hash(leaves[k:])]
    return audit_path(leaves[k:], index - k) + [root_hash(leaves[:k])]


def verify_inclusion(leaf: bytes, index: int, size: int, proof, root: bytes) -> bool:
    """Recompute the root from the leaf and its path; compare with `root`.

    `proof` is a list of sibling hashes (bytes), bottom-up. Malformed inputs
    return False rather than raise: a verifier that throws on hostile input is
    a verifier that can be turned off by one bad package.
    """
    try:
        if not isinstance(size, int) or size <= 0:
            return False
        if not 0 <= index < size:
            return False
        fn, sn, r = index, size - 1, leaf
        for sibling in proof:
            if not isinstance(sibling, (bytes, bytearray)) or len(sibling) != 32:
                return False
            if fn % 2 == 1 or fn == sn:
                r = node_hash(bytes(sibling), r)
                while fn % 2 == 0 and fn != 0:
                    fn //= 2
                    sn //= 2
            else:
                r = node_hash(r, bytes(sibling))
            fn //= 2
            sn //= 2
        return r == root and sn == 0
    except Exception:
        return False


def build_proof(leaves, index):
    """Audit path as lowercase hex, for putting in a package."""
    return [h.hex() for h in audit_path(leaves, index)]
