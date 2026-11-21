"""Merkle consistency proofs (RFC 6962 §2.1.2), built and checked by us.

Why these exist: on 2026-11-21 we measured ourselves against the PyPI
`scitt-cose` substrate. Its Merkle roots matched ours byte for byte on five
tree sizes and our `verify_inclusion` accepted all nine of its audit paths —
but our module had no consistency proof at all, so a log that grew could not
be checked with us. This file closes that hole and pins the behaviour:

- a proof we build must verify against our own verifier (round trip);
- a tampered proof, a wrong root, or a wrong size pair must be refused;
- hostile input (wrong length, wrong types) returns False, never raises.

The algorithm is RFC 6962: `SUBPROOF(m, D[lo:lo+n], b)`, and verification is
the Trillian shape — walk bottom-up, folding the right subtree by itself and
the shifted subtree into both accumulators.
"""
import unittest

from uibc_core import merkle


def _hashed(size, profile="rfc6962"):
    """Leaf hashes for `size` distinguishable leaves."""
    return [merkle.leaf_hash(("leaf-%d" % i).encode(), profile) for i in range(size)]


class TestRoundTrip(unittest.TestCase):
    def test_proof_we_build_verifies(self):
        for size in (1, 2, 3, 5, 8, 9, 16, 17):
            leaves = _hashed(size)
            second = merkle.root_hash(leaves)
            for first in range(1, size + 1):
                proof = merkle.build_consistency_proof(leaves, first)
                first_root = merkle.root_hash(leaves[:first])
                self.assertTrue(
                    merkle.verify_consistency(first_root, first, second, size,
                                              [bytes.fromhex(h) for h in proof]),
                    "size=%d first=%d proof=%r" % (size, first, proof))

    def test_same_size_needs_no_proof(self):
        leaves = _hashed(5)
        root = merkle.root_hash(leaves)
        self.assertTrue(merkle.verify_consistency(root, 5, root, 5, []))
        self.assertEqual(merkle.build_consistency_proof(leaves, 5), [])

    def test_same_size_with_a_proof_is_refused(self):
        leaves = _hashed(5)
        root = merkle.root_hash(leaves)
        self.assertFalse(merkle.verify_consistency(root, 5, root, 5, [root]))


class TestRefusals(unittest.TestCase):
    def setUp(self):
        self.leaves = _hashed(9)
        self.first, self.second = 4, 9
        self.first_root = merkle.root_hash(self.leaves[:self.first])
        self.second_root = merkle.root_hash(self.leaves)
        self.proof = [bytes.fromhex(h) for h in
                      merkle.build_consistency_proof(self.leaves, self.first)]

    def test_tampered_node_is_refused(self):
        bad = list(self.proof)
        bad[0] = bytes([bad[0][0] ^ 0x01]) + bad[0][1:]
        self.assertFalse(merkle.verify_consistency(
            self.first_root, self.first, self.second_root, self.second, bad))

    def test_wrong_first_root_is_refused(self):
        other = merkle.root_hash(_hashed(3))
        self.assertFalse(merkle.verify_consistency(
            other, self.first, self.second_root, self.second, self.proof))

    def test_wrong_size_pair_is_refused(self):
        self.assertFalse(merkle.verify_consistency(
            self.first_root, self.first, self.second_root, self.second - 1, self.proof))

    def test_dropping_a_node_is_refused(self):
        self.assertFalse(merkle.verify_consistency(
            self.first_root, self.first, self.second_root, self.second, self.proof[1:]))

    def test_hostile_shapes_return_false_and_never_raise(self):
        self.assertFalse(merkle.verify_consistency(
            self.first_root, self.first, self.second_root, self.second, [b"\x00" * 31]))
        self.assertFalse(merkle.verify_consistency(
            self.first_root, self.first, self.second_root, self.second, ["not-bytes"]))
        self.assertFalse(merkle.verify_consistency(
            b"\x00" * 31, self.first, self.second_root, self.second, self.proof))
        self.assertFalse(merkle.verify_consistency(
            self.first_root, 0, self.second_root, self.second, self.proof))
        # m == 0 with an empty proof is the RFC convention: consistent.
        self.assertTrue(merkle.verify_consistency(
            self.first_root, 0, self.second_root, self.second, []))
        self.assertFalse(merkle.verify_consistency(
            self.first_root, self.second, self.second_root, self.first, self.proof))


class TestAer1RefusesConsistency(unittest.TestCase):
    def test_aer1_says_no_instead_of_guessing(self):
        leaves = _hashed(4, "aer1")
        root = merkle.root_hash(leaves, "aer1")
        self.assertFalse(merkle.verify_consistency(root, 2, root, 4, [],
                                                   profile="aer1"))


if __name__ == "__main__":
    unittest.main()
