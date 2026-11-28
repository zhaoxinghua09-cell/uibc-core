"""The log we operate ourselves: leaves, checkpoints, witnesses, proofs.

Three things these tests refuse to let slide:
  1. an inclusion proof is checked by **somebody else's** code (the vendored Trillian
     verifier in `tools/third_party/sigstore_merkle.py`), not only by ours. A proof
     that only its own producer can verify proves nothing to a stranger.
  2. a cosignature must not verify on a different head. A witness that "signs
     whatever the operator signed" is a rubber stamp; the domain separation has to
     actually bite.
  3. a shortened log must fail against the committed head. Truncation is the attack
     an append-only log exists to catch.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "third_party"))

from uibc_core import ed25519, merkle, translog as T   # noqa: E402

OPERATOR = bytes.fromhex("11" * 32)
WITNESS_A = bytes.fromhex("22" * 32)
WITNESS_B = bytes.fromhex("33" * 32)


def build(n):
    log = T.new_log()
    for i in range(n):
        T.append(log, {"record": i, "what": "fixture"})
    return log


class Leaves(unittest.TestCase):
    def test_digest_is_stable_and_order_sensitive(self):
        a = T.record_digest({"x": 1})
        self.assertEqual(a, T.record_digest({"x": 1}))
        self.assertNotEqual(a, T.record_digest({"x": 2}))

    def test_empty_log_root_is_rfc6962_empty_root(self):
        log = T.new_log()
        self.assertEqual(T.root_hex(log), merkle.root_hash([]).hex())
        self.assertEqual(T.root_hex(log), "e3b0c44298fc1c149afbf4c8996fb924"
                                          "27ae41e4649b934ca495991b7852b855")

    def test_append_returns_index_and_grows(self):
        log = T.new_log()
        _, i0 = T.append(log, {"a": 1})
        _, i1 = T.append(log, {"a": 2})
        self.assertEqual((i0, i1), (0, 1))
        self.assertEqual(T.tree_size(log), 2)


class Checkpoints(unittest.TestCase):
    def test_unsigned_checkpoint_still_commits(self):
        cp = T.checkpoint(build(3))
        self.assertEqual(cp["tree_size"], 3)
        self.assertEqual(cp["root"], T.root_hex(build(3)))
        self.assertNotIn("sig", cp)

    def test_operator_signature_verifies_and_is_bound_to_the_head(self):
        log = build(3)
        cp = T.checkpoint(log, OPERATOR, note="fixture")
        self.assertTrue(T.verify_checkpoint(cp, ed25519.publickey(OPERATOR)))
        cp2 = dict(cp, tree_size=2, root=T.root_hex(build(2)))   # same sig, different head
        self.assertFalse(T.verify_checkpoint(cp2, ed25519.publickey(OPERATOR)))

    def test_checkpoint_hash_names_the_head(self):
        cp = T.checkpoint(build(4))
        same = T.checkpoint(build(4))
        self.assertEqual(T.checkpoint_hash(cp), T.checkpoint_hash(same))
        self.assertNotEqual(T.checkpoint_hash(cp), T.checkpoint_hash(T.checkpoint(build(5))))

    def test_cosignature_verifies_for_its_witness_only(self):
        cp = T.checkpoint(build(4), OPERATOR)
        cos = T.cosign(cp, WITNESS_A)
        self.assertTrue(T.verify_cosignature(cp, cos, ed25519.publickey(WITNESS_A)))
        self.assertFalse(T.verify_cosignature(cp, cos, ed25519.publickey(WITNESS_B)))

    def test_cosignature_does_not_carry_over_to_another_head(self):
        cp4 = T.checkpoint(build(4), OPERATOR)
        cos = T.cosign(cp4, WITNESS_A)
        cp5 = T.checkpoint(build(5), OPERATOR)
        self.assertFalse(T.verify_cosignature(cp5, cos, ed25519.publickey(WITNESS_A)))

    def test_operator_cosigning_itself_is_not_counted_as_a_witness(self):
        """A cosignature with the operator's own key is a valid signature and a
        worthless witness. It must therefore not appear in a witness summary
        whose expected witness keys are those of other parties."""
        cp = T.checkpoint(build(2), OPERATOR)
        selfcos = T.cosign(cp, OPERATOR)          # operator signing as itself
        self.assertTrue(T.verify_cosignature(cp, selfcos, ed25519.publickey(OPERATOR)))
        s = T.witness_summary(cp, [selfcos], [ed25519.publickey(WITNESS_A)])
        self.assertEqual((s["valid"], s["invalid"]), (0, 1))

    def test_witness_summary_counts_rather_than_assumes(self):
        cp = T.checkpoint(build(3), OPERATOR)
        cos = [T.cosign(cp, WITNESS_A), T.cosign(cp, WITNESS_B)]
        s = T.witness_summary(cp, cos, [ed25519.publickey(WITNESS_A), ed25519.publickey(WITNESS_B)])
        self.assertEqual(s["valid"], 2)
        s2 = T.witness_summary(cp, cos, [ed25519.publickey(WITNESS_A), ed25519.publickey(OPERATOR)])
        self.assertEqual((s2["valid"], s2["invalid"]), (1, 1))


class Proofs(unittest.TestCase):
    def test_inclusion_holds_for_every_index_and_size(self):
        for n in range(1, 18):
            log = build(n)
            for i in range(n):
                with self.subTest(size=n, index=i):
                    self.assertTrue(T.verify_inclusion(log, i, T.inclusion_proof(log, i)))

    def test_inclusion_fails_for_wrong_index_or_wrong_leaf(self):
        log = build(6)
        proof = T.inclusion_proof(log, 2)
        self.assertFalse(T.verify_inclusion(log, 3, proof))
        other = build(6)
        T.append(other, {"record": 99})
        self.assertFalse(T.verify_inclusion(other, 2, proof))

    def test_a_shortened_log_does_not_match_the_committed_head(self):
        """Truncation: the committed checkpoint is the out-of-band head that catches it."""
        full = build(8)
        cp = T.checkpoint(full, OPERATOR)
        short = build(7)
        self.assertNotEqual(T.root_hex(short), cp["root"])
        self.assertFalse(T.verify_checkpoint(dict(cp, root=T.root_hex(short)), ed25519.publickey(OPERATOR)))

    def test_consistency_proof_between_two_heads(self):
        old = build(3)
        new = build(9)
        proof = T.consistency_proof(old, new)
        self.assertTrue(T.verify_consistency(old, T.checkpoint(new), proof))
        self.assertFalse(T.verify_consistency(build(4), T.checkpoint(new), proof))

    def test_foreign_implementation_checks_our_inclusion_proof(self):
        """Independent judge: Sigstore's vendored Trillian verifier, not our code."""
        from sigstore_merkle import verify_merkle_inclusion, VerificationError

        class P:
            pass

        log = build(7)
        idx = 4
        stub = P()
        stub._inner = P()
        # The vendored verifier hashes 0x00 || canonicalized_body, the same leaf rule.
        stub._inner.canonicalized_body = bytes.fromhex(log["entries"][idx])
        stub._inner.inclusion_proof = P()
        stub._inner.inclusion_proof.log_index = idx
        stub._inner.inclusion_proof.tree_size = T.tree_size(log)
        stub._inner.inclusion_proof.hashes = T.inclusion_proof(log, idx)
        stub._inner.inclusion_proof.root_hash = T.root_hash_bytes(log)
        verify_merkle_inclusion(stub)          # raises on failure

        stub._inner.inclusion_proof.root_hash = bytes.fromhex(merkle.root_hash([]).hex())
        with self.assertRaises(VerificationError):
            verify_merkle_inclusion(stub)


class Journal(unittest.TestCase):
    def test_jsonl_round_trips_and_refuses_a_gap(self):
        log = build(5)
        back = T.from_jsonl(T.to_jsonl(log))
        self.assertEqual(back["entries"], log["entries"])
        self.assertEqual(T.root_hex(back), T.root_hex(log))
        lines = T.to_jsonl(log).splitlines()
        del lines[2]
        with self.assertRaises(ValueError):
            T.from_jsonl("\n".join(lines) + "\n")

    def test_journal_is_diffable_appends_only(self):
        """Growing the log must only add lines; a rewrite of earlier lines is visible."""
        small = T.to_jsonl(build(3)).splitlines()
        big = T.to_jsonl(build(5)).splitlines()
        self.assertEqual(big[:3], small)


if __name__ == "__main__":
    unittest.main(verbosity=2)
