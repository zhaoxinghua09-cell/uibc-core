"""Cross-implementation check: our Merkle code vs an independent RFC 6962 build.

Why this exists: "we verify Merkle inclusion proofs" is one of the four claims we
put in front of outsiders, so it cannot rest on our own tests alone - a wrong
implementation that is wrong consistently passes its own suite. This file
implements RFC 6962 a second time, from the spec text, with different recursion
(root split by the largest power of two below n) and a verifier written without
compaction, then asserts agreement on root, proof and both verifiers across tree
sizes 1..39 and a few large ones.

It also settled a live question on 2026-11-17: Rekor's inclusion proof failed
against our verifier, and this check proved the failure was in Rekor's partial
proof, not in our arithmetic.
"""

import hashlib
import unittest

from uibc_core import merkle


def _leaf(d):
    return hashlib.sha256(b"\x00" + d).digest()


def _node(l, r):
    return hashlib.sha256(b"\x01" + l + r).digest()


def ref_root(datas):
    n = len(datas)
    if n == 0:
        return hashlib.sha256(b"").digest()
    if n == 1:
        return _leaf(datas[0])
    k = 1
    while k * 2 < n:
        k *= 2
    return _node(ref_root(datas[:k]), ref_root(datas[k:]))


def ref_proof(datas, index):
    n = len(datas)
    if n == 1:
        return []
    k = 1
    while k * 2 < n:
        k *= 2
    if index < k:
        return ref_proof(datas[:k], index) + [ref_root(datas[k:])]
    return ref_proof(datas[k:], index - k) + [ref_root(datas[:k])]


def ref_verify(leaf_hash, index, size, proof, root):
    if size <= 0 or not 0 <= index < size:
        return False
    fn, sn = index, size - 1
    r = leaf_hash
    for p in proof:
        if fn % 2 == 1 or fn == sn:
            r = _node(p, r)
            while fn % 2 == 0 and fn != 0:
                fn //= 2
                sn //= 2
        else:
            r = _node(r, p)
        fn //= 2
        sn //= 2
    return r == root and sn == 0


SIZES = list(range(1, 40)) + [64, 100, 257, 1000]


class MerkleAgainstReferenceTests(unittest.TestCase):
    def test_roots_agree(self):
        for n in SIZES:
            datas = [("leaf-%d-%d" % (n, i)).encode() for i in range(n)]
            our = merkle.root_hash([merkle.leaf_hash(d) for d in datas])
            ref = ref_root(datas)
            self.assertEqual(our, ref, "root differs at n=%d" % n)

    def test_proofs_and_verifiers_agree(self):
        for n in SIZES:
            datas = [("leaf-%d-%d" % (n, i)).encode() for i in range(n)]
            leaves = [merkle.leaf_hash(d) for d in datas]
            root = ref_root(datas)
            for i in sorted({0, n // 2, n - 1}):
                if i >= n:
                    continue
                ours = [bytes.fromhex(h) for h in merkle.build_proof(leaves, i)]
                self.assertEqual(ours, ref_proof(datas, i),
                                 "proof differs at n=%d i=%d" % (n, i))
                self.assertTrue(ref_verify(leaves[i], i, n, ours, root))
                self.assertTrue(merkle.verify_inclusion(leaves[i], i, n, ours, root),
                                "our verifier rejected a proof it built (n=%d i=%d)" % (n, i))

    def test_wrong_index_is_rejected_by_both(self):
        n = 1000
        datas = [("x-%d" % i).encode() for i in range(n)]
        leaves = [merkle.leaf_hash(d) for d in datas]
        root = ref_root(datas)
        proof = [bytes.fromhex(h) for h in merkle.build_proof(leaves, 500)]
        self.assertFalse(merkle.verify_inclusion(leaves[500], 499, n, proof, root))
        self.assertFalse(ref_verify(leaves[500], 499, n, proof, root))

    def test_duplicated_tail_cannot_forge_a_root(self):
        # The classic bug: duplicating the odd leaf to make a power of two.
        # Both trees must give different roots, and ours must not match the fake.
        datas = [b"a", b"b", b"c"]
        leaves = [merkle.leaf_hash(d) for d in datas]
        real = merkle.root_hash(leaves)
        fake = merkle.root_hash(leaves + [leaves[-1]])
        self.assertNotEqual(real, fake)


if __name__ == "__main__":
    unittest.main()
