"""Merkle inclusion proofs, standard library only, with selectable profiles.

Why this exists: the AER-1 conformance corpus has a whole class we had nothing
for - `base/merkle-vectors.json`, 9 vectors / 12 checks. A hash chain answers
"was file N changed?"; a Merkle tree answers "is this one file inside a set of
size N that you committed to, without my handing you all N files?" Those are
different questions and only the second one scales to a device with thousands
of evidence objects.

Two constructions are available, selected by name:

`profile="rfc6962"` (default, unchanged)
    RFC 6962, the Certificate Transparency tree:
        leaf hash  = SHA-256(0x00 || leaf_bytes)
        node hash  = SHA-256(0x01 || left || right)
        an unbalanced tail is promoted, not duplicated - duplicating it would
        make two different trees share a root, which is the classic mistake.

`profile="aer1"`
    draft-zambo-aer1 Section 8.1, so that the AER-1 vectors can be run through
    this implementation unchanged:
        leaf hash  = SHA-256(UTF-8 bytes of receipt_id), no prefix
        node hash  = SHA-256(raw 32-byte left || raw 32-byte right), no prefix
        an odd node is duplicated level by level
        empty tree = SHA-256 of the empty input (e3b0c442...)

The two constructions differ in all three parameters, so a root computed under
one cannot be re-verified under the other - that is a construction difference,
not an implementation error, and it is why the profile is a named option rather
than a silent switch. Nothing here changes the default: callers that do not
name a profile get exactly the bytes they got before.

Proofs are index-addressed, so a verifier needs: the leaf, its index, the tree
size, the sibling path, and the root it was told out of band.
"""

import hashlib

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"

PROFILE_RFC6962 = "rfc6962"
PROFILE_AER1 = "aer1"
DEFAULT_PROFILE = PROFILE_RFC6962
PROFILES = (PROFILE_RFC6962, PROFILE_AER1)


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _check_profile(profile: str) -> str:
    if profile not in PROFILES:
        raise ValueError(
            "unknown Merkle profile %r; expected one of %s" % (profile, ", ".join(PROFILES))
        )
    return profile


def _as_bytes(data) -> bytes:
    """Accept a receipt_id string or bytes; the spec hashes UTF-8 bytes."""
    if isinstance(data, str):
        return data.encode("utf-8")
    return bytes(data)


def leaf_hash(data, profile: str = DEFAULT_PROFILE) -> bytes:
    _check_profile(profile)
    data = _as_bytes(data)
    if profile == PROFILE_AER1:
        return _sha256(data)
    return _sha256(LEAF_PREFIX + data)


def node_hash(left: bytes, right: bytes, profile: str = DEFAULT_PROFILE) -> bytes:
    _check_profile(profile)
    if profile == PROFILE_AER1:
        return _sha256(bytes(left) + bytes(right))
    return _sha256(NODE_PREFIX + left + right)


def _largest_pow2_below(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def _root_aer1(leaves):
    """Section 8.1 tree: pair level by level, duplicate the odd node."""
    level = list(leaves)
    if not level:
        return _sha256(b"")
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(node_hash(left, right, PROFILE_AER1))
        level = nxt
    return level[0]


def root_hash(leaves, profile: str = DEFAULT_PROFILE) -> bytes:
    """Merkle root over already-hashed leaves.

    rfc6962: empty tree -> all-zero digest (the historical convention here).
    aer1:    empty tree -> SHA-256 of the empty input, per Section 8.1.
    """
    _check_profile(profile)
    leaves = list(leaves)
    if profile == PROFILE_AER1:
        return _root_aer1(leaves)
    if not leaves:
        return b"\x00" * 32
    if len(leaves) == 1:
        return leaves[0]
    k = _largest_pow2_below(len(leaves))
    return node_hash(root_hash(leaves[:k]), root_hash(leaves[k:]))


def root_from_data(items, profile: str = DEFAULT_PROFILE) -> str:
    """Root over raw items (bytes, or str receipt_ids) as lowercase hex."""
    _check_profile(profile)
    return root_hash([leaf_hash(i, profile) for i in items], profile).hex()


def _depth_aer1(size: int) -> int:
    depth, width = 0, size
    while width > 1:
        width = (width + 1) // 2
        depth += 1
    return depth


def audit_path(leaves, index: int, profile: str = DEFAULT_PROFILE):
    """Sibling hashes from the leaf up to the root, bottom-up."""
    _check_profile(profile)
    leaves = list(leaves)
    if profile == PROFILE_AER1:
        if not 0 <= index < len(leaves):
            raise IndexError("leaf index out of range")
        level, idx, path = list(leaves), index, []
        while len(level) > 1:
            if len(level) % 2:
                level.append(level[-1])
            sibling = level[idx + 1] if idx % 2 == 0 else level[idx - 1]
            path.append(sibling)
            level = [
                node_hash(level[i], level[i + 1], PROFILE_AER1)
                for i in range(0, len(level), 2)
            ]
            idx //= 2
        return path
    if not 0 <= index < len(leaves):
        raise IndexError("leaf index out of range")
    if len(leaves) == 1:
        return []
    k = _largest_pow2_below(len(leaves))
    if index < k:
        return audit_path(leaves[:k], index) + [root_hash(leaves[k:])]
    return audit_path(leaves[k:], index - k) + [root_hash(leaves[:k])]


def _verify_aer1(leaf: bytes, index: int, size: int, proof, root: bytes) -> bool:
    if not 0 <= index < size:
        return False
    if len(proof) != _depth_aer1(size):
        return False
    r, idx = leaf, index
    for sibling in proof:
        if not isinstance(sibling, (bytes, bytearray)) or len(sibling) != 32:
            return False
        r = node_hash(r, sibling, PROFILE_AER1) if idx % 2 == 0 else node_hash(sibling, r, PROFILE_AER1)
        idx //= 2
    return r == root


def verify_inclusion(leaf: bytes, index: int, size: int, proof, root: bytes,
                     profile: str = DEFAULT_PROFILE) -> bool:
    """Recompute the root from the leaf and its path; compare with `root`.

    `proof` is a list of sibling hashes (bytes), bottom-up. Malformed inputs
    return False rather than raise: a verifier that throws on hostile input is
    a verifier that can be turned off by one bad package.
    """
    try:
        _check_profile(profile)
        if not isinstance(size, int) or size <= 0:
            return False
        if not 0 <= index < size:
            return False
        if profile == PROFILE_AER1:
            return _verify_aer1(leaf, index, size, proof, root)
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


def build_proof(leaves, index: int, profile: str = DEFAULT_PROFILE):
    """Audit path as lowercase hex, for putting in a package."""
    return [h.hex() for h in audit_path(leaves, index, profile)]


def _subproof(hashes, lo: int, n: int, m: int, b: bool, profile: str):
    """RFC 6962 §2.1.2 SUBPROOF(m, D[lo:lo+n], b) over already-hashed leaves."""
    if m == n:
        return [] if b else [root_hash(hashes[lo:lo + n], profile)]
    k = _largest_pow2_below(n)
    if m <= k:
        return (_subproof(hashes, lo, k, m, b, profile)
                + [root_hash(hashes[lo + k:lo + n], profile)])
    return (_subproof(hashes, lo + k, n - k, m - k, False, profile)
            + [root_hash(hashes[lo:lo + k], profile)])


def build_consistency_proof(leaves, first_size: int, profile: str = DEFAULT_PROFILE):
    """Consistency proof between the first `first_size` leaves and all of them.

    `leaves` are leaf **hashes** (bytes), the same currency `audit_path` and
    `root_hash` use. Returns lowercase hex, bottom-up, ready for a package.
    RFC 6962 §2.1.2: proves the size-`first_size` tree is a prefix of the
    bigger one.
    """
    _check_profile(profile)
    leaves = list(leaves)
    n, m = len(leaves), int(first_size)
    if m <= 0 or m > n:
        raise ValueError("first_size must be in 1..len(leaves)")
    if m == n:
        return []
    return [h.hex() for h in _subproof(leaves, 0, n, m, True, profile)]


def verify_consistency(first_root: bytes, first_size: int, second_root: bytes,
                       second_size: int, proof, profile: str = DEFAULT_PROFILE) -> bool:
    """Check a consistency proof without trusting the prover.

    Same discipline as `verify_inclusion`: malformed or hostile input returns
    False, never raises. Two trees of the same size are consistent iff the
    roots are equal and the proof is empty.
    """
    try:
        _check_profile(profile)
        if profile == PROFILE_AER1:
            return False  # AER-1 has no consistency-proof shape yet; refuse rather than guess
        if not isinstance(first_size, int) or not isinstance(second_size, int):
            return False
        if first_size < 0 or second_size < first_size:
            return False
        nodes = []
        for node in proof:
            if not isinstance(node, (bytes, bytearray)) or len(node) != 32:
                return False
            nodes.append(bytes(node))
        if first_size == 0:
            # The empty old tree is a prefix of anything; RFC wants no proof.
            return not nodes
        if not isinstance(first_root, (bytes, bytearray)) or len(first_root) != 32:
            return False
        if not isinstance(second_root, (bytes, bytearray)) or len(second_root) != 32:
            return False
        if first_size == second_size:
            return not nodes and bytes(first_root) == bytes(second_root)
        if first_size & (first_size - 1) == 0:
            # Perfect subtree: its root stands in for the omitted first node.
            nodes = [bytes(first_root)] + nodes
        if not nodes:
            return False
        fn, sn = first_size - 1, second_size - 1
        while fn % 2 == 1:      # step past the shared right edge
            fn //= 2
            sn //= 2
        fr = sr = nodes[0]
        for node in nodes[1:]:
            if sn == 0:
                return False
            if fn % 2 == 1 or fn == sn:
                # This node sits to the LEFT of both running roots.
                fr = node_hash(node, fr, profile)
                sr = node_hash(node, sr, profile)
                while fn % 2 == 0 and fn != 0:
                    fn //= 2
                    sn //= 2
            else:
                # To the RIGHT of the newer root only.
                sr = node_hash(sr, node, profile)
            fn //= 2
            sn //= 2
        return fr == bytes(first_root) and sr == bytes(second_root) and sn == 0
    except Exception:
        return False

