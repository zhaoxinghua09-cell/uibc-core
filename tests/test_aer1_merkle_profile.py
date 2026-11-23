"""AER-1 Section 8.1: the nine vectors must pass under the named `aer1` profile.

Why this exists: the AER-1 corpus class `base/merkle-vectors.json` (9 vectors /
12 checks) was the one class where our implementation produced nothing the
corpus could verify. The run of 2026-11-19 showed 0 of 9 roots agree between the
two constructions - a construction difference in three parameters, not an
arithmetic error. Brennan Zambo (AER-1 author) accepted a named profile so that
the vectors pass unchanged and both constructions can sit side by side in one
implementation.

The vectors file is the corpus fixture, byte-identical to kit 1.5.7
(sha256 8c76473616ba909fab61cdb96d3e432f3e91b322833716d494e7afc92ad13a25, LF) and is
not edited here: if it were edited to fit our code, the test would prove nothing.

The default construction must be untouched: the last check in this file asserts
that the same nine vectors still give 0 of 9 under `rfc6962`, which is the
property the profile exists to keep visible.
"""

import hashlib
import json
import os
import unittest

from uibc_core import merkle

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "aer1-merkle-vectors.json")
FIXTURE_SHA256 = "8c76473616ba909fab61cdb96d3e432f3e91b322833716d494e7afc92ad13a25"


def _load():
    with open(FIXTURE, "rb") as fh:
        raw = fh.read()
    # The pin is on content, not on line endings. A checkout with
    # `core.autocrlf=true` (the Windows default) rewrites CRLF into this JSON
    # fixture, and a byte-exact pin then fails on nine tests for a reason that has
    # nothing to do with the vectors. Found 2026-11-22 by running the suite on a
    # plain Windows checkout for the first time.
    canonical = raw.replace(b"\r\n", b"\n")
    assert hashlib.sha256(canonical).hexdigest() == FIXTURE_SHA256, "fixture drifted from kit 1.5.7"
    return json.loads(canonical.decode("utf-8"))


def _leaves_for(vector):
    """Leaf digests for a vector, under the 8.1 rule (unprefixed SHA-256)."""
    if "receipt_ids" in vector:
        return [merkle.leaf_hash(rid, merkle.PROFILE_AER1) for rid in vector["receipt_ids"]]
    return [
        merkle.leaf_hash(leaf["preimage"], merkle.PROFILE_AER1)
        for leaf in vector.get("leaves", [])
    ]


class Aer1VectorsTest(unittest.TestCase):
    def setUp(self):
        self.doc = _load()

    def test_fixture_is_kit_1_5_7(self):
        self.assertEqual(self.doc["vectors"][0]["name"], "canonical-5-step")
        self.assertEqual(len(self.doc["vectors"]), 9)

    def test_every_vector_root_matches_expected(self):
        for vector in self.doc["vectors"]:
            leaves = _leaves_for(vector)
            root = merkle.root_hash(leaves, merkle.PROFILE_AER1).hex()
            self.assertEqual(root, vector["expected_root"], vector["name"])
            if "must_not_equal" in vector:
                self.assertNotEqual(root, vector["must_not_equal"], vector["name"])

    def test_root_from_receipt_ids_reaches_same_root(self):
        """The public entry point, ids straight in - no hand-hashing in the test."""
        for vector in self.doc["vectors"]:
            if "receipt_ids" not in vector:
                continue
            self.assertEqual(
                merkle.root_from_data(vector["receipt_ids"], merkle.PROFILE_AER1),
                vector["expected_root"],
                vector["name"],
            )

    def test_empty_tree_root_is_sha256_of_empty_input(self):
        self.assertEqual(
            merkle.root_hash([], merkle.PROFILE_AER1).hex(),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_duplicate_receipt_id_vector_collides_at_tree_level(self):
        """8.2 (package layer, check S12) is what rejects this, not the tree."""
        vector = [v for v in self.doc["vectors"] if v["name"] == "duplicate-receipt-id-collision"][0]
        self.assertEqual(
            merkle.root_from_data(vector["receipt_ids"], merkle.PROFILE_AER1),
            vector["expected_root"],
        )
        self.assertEqual(vector["expected_workflow_verdict"], "invalid")

    def test_inclusion_proofs_round_trip_under_profile(self):
        for vector in self.doc["vectors"]:
            leaves = _leaves_for(vector)
            if not leaves:
                continue
            root = merkle.root_hash(leaves, merkle.PROFILE_AER1)
            for index, leaf in enumerate(leaves):
                proof = merkle.audit_path(leaves, index, merkle.PROFILE_AER1)
                self.assertTrue(
                    merkle.verify_inclusion(leaf, index, len(leaves), proof, root,
                                            merkle.PROFILE_AER1),
                    "%s index %d" % (vector["name"], index),
                )

    def test_inclusion_negative_controls(self):
        ids = ["e80168eb-a6a1-4ec9-8478-ac108f9397ff",
               "514fe841-bbdd-4804-9ef4-6828842d8763",
               "a090bdad-f2cf-48c9-bc89-e9e17700fb15"]
        leaves = [merkle.leaf_hash(i, merkle.PROFILE_AER1) for i in ids]
        root = merkle.root_hash(leaves, merkle.PROFILE_AER1)
        proof = merkle.audit_path(leaves, 0, merkle.PROFILE_AER1)
        # wrong index
        self.assertFalse(merkle.verify_inclusion(leaves[0], 1, 3, proof, root,
                                                 merkle.PROFILE_AER1))
        # wrong leaf
        self.assertFalse(merkle.verify_inclusion(leaves[1], 0, 3, proof, root,
                                                 merkle.PROFILE_AER1))
        # wrong root
        self.assertFalse(merkle.verify_inclusion(leaves[0], 0, 3, proof, b"\x00" * 32,
                                                 merkle.PROFILE_AER1))
        # truncated proof
        self.assertFalse(merkle.verify_inclusion(leaves[0], 0, 3, proof[:-1], root,
                                                 merkle.PROFILE_AER1))

    def test_default_construction_still_disagrees_on_all_nine(self):
        """The property the profile exists to keep visible: 0 of 9 under rfc6962."""
        agree = 0
        for vector in self.doc["vectors"]:
            if "receipt_ids" not in vector or not vector["receipt_ids"]:
                continue
            if merkle.root_from_data(vector["receipt_ids"]) == vector["expected_root"]:
                agree += 1
        self.assertEqual(agree, 0)

    def test_unknown_profile_is_refused(self):
        with self.assertRaises(ValueError):
            merkle.root_from_data(["a"], "merkle-2019")


if __name__ == "__main__":
    unittest.main()
