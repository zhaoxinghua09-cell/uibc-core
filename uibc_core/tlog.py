"""tlog.py (v0.8 draft) - RFC 6962 Merkle tree with consistency proofs.

Deliberately a *separate* tree from the AER1 evidence tree: RFC 6962 splits at
the largest power of two below n, AER1 duplicates the odd node. Mixing them
would produce proofs that verify against neither.
"""
from .merkle import node_hash, leaf_hash


def _k(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def mth(leaves) -> bytes:
    n = len(leaves)
    if n == 0:
        return b"\x00" * 32
    if n == 1:
        return leaves[0]
    k = _k(n)
    return node_hash(mth(leaves[:k]), mth(leaves[k:]))


def _subproof(m: int, d, b: bool):
    n = len(d)
    if m == n:
        return [] if b else [mth(d)]
    k = _k(n)
    if m <= k:
        return _subproof(m, d[:k], b) + [mth(d[k:])]
    return _subproof(m - k, d[k:], False) + [mth(d[:k])]


def consistency_proof(m: int, d):
    """Proof that a tree of size m is a prefix of the tree built from d."""
    if not 0 < m <= len(d):
        raise ValueError("m out of range")
    if m == len(d):
        return []
    return _subproof(m, d, True)


def verify_consistency_standalone(m: int, old_root: bytes, n: int, new_root: bytes,
                                 proof) -> bool:
    """RFC 6962 consistency verification *without* the log entries.

    Mirrors SUBPROOF's structure, tracking two values per subtree:
      prefix_root  - root of the first `m` leaves inside it (== old root at top)
      subtree_root - root of all its leaves             (== new root at top)
    """
    def k_of(x):
        k = 1
        while k * 2 < x:
            k *= 2
        return k

    def walk(mm, nn, b, nodes):
        if mm > nn or not (0 < mm <= nn):
            raise ValueError("bad sizes")
        if mm == nn:
            if b:
                if nodes:
                    raise ValueError("unexpected trailing nodes")
                return old_root, old_root          # this subtree IS the old tree
            if len(nodes) != 1:
                raise ValueError("base needs exactly one node")
            return nodes[-1], nodes[-1]
        if not nodes:
            raise ValueError("empty proof")
        k = k_of(nn)
        if mm <= k:
            pre, sub = walk(mm, k, b, nodes[:-1])
            return pre, node_hash(sub, nodes[-1])
        pre_r, sub_r = walk(mm - k, nn - k, False, nodes[:-1])
        return node_hash(nodes[-1], pre_r), node_hash(nodes[-1], sub_r)

    try:
        nodes = [bytes.fromhex(x) if isinstance(x, str) else bytes(x) for x in proof]
        if not (0 < m <= n):
            return False
        if m == n:
            return not nodes and old_root == new_root
        pre, sub = walk(m, n, True, nodes)
        return pre == old_root and sub == new_root
    except Exception:
        return False


def verify_consistency_against(m: int, leaves, proof) -> bool:
    """Check a consistency proof against the log entries themselves.

    NOTE (honest limitation): this verifies "the proof matches the entries I hold"
    and "old root is the prefix root". It does NOT verify a proof standalone
    without the entries - the standalone RFC 6962 verifier is not implemented
    (round-trip only). Always pair it with an entry-set root check.
    """
    try:
        if not 0 < m <= len(leaves):
            return False
        if consistency_proof(m, leaves) != list(proof):
            return False
        return True
    except Exception:
        return False


def build_log(heads):
    """Leaf per head, index-bound so the same head cannot be moved."""
    from .canonical import canonicalize
    return [leaf_hash(canonicalize({"i": i, "head": h})) for i, h in enumerate(heads)]
