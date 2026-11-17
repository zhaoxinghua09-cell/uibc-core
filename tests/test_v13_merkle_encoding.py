"""S13 Merkle inclusion + S14 strict base64 (v1.1).

Two classes the AER-1 corpus marks must-fail that we had no answer for:
`base/merkle-vectors.json` (9 vectors / 12 checks) and the four base64 classes.
These tests assert the *behaviour* (must reject) rather than the implementation,
so the code can be rewritten underneath them.
"""

import json
import os
import shutil
import tempfile
import unittest

from uibc_core import encoding, merkle
from uibc_core.verify import verify

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "fixtures", "clean.uibc")


class MerkleTests(unittest.TestCase):
    def test_root_is_deterministic_and_order_sensitive(self):
        a = [b"one", b"two", b"three", b"four"]
        r1 = merkle.root_from_data(a)
        r2 = merkle.root_from_data(a)
        self.assertEqual(r1, r2)
        self.assertNotEqual(r1, merkle.root_from_data([b"two", b"one", b"three", b"four"]))

    def test_inclusion_proof_verifies_for_every_index(self):
        data = [("f%02d" % i).encode() for i in range(9)]
        leaves = [merkle.leaf_hash(d) for d in data]
        root = merkle.root_hash(leaves)
        for i in range(len(leaves)):
            proof = [bytes.fromhex(h) for h in merkle.build_proof(leaves, i)]
            self.assertTrue(merkle.verify_inclusion(leaves[i], i, len(leaves), proof, root),
                            "index %d should verify" % i)

    def test_tampered_leaf_or_index_fails(self):
        data = [b"a", b"b", b"c", b"d", b"e"]
        leaves = [merkle.leaf_hash(d) for d in data]
        root = merkle.root_hash(leaves)
        proof = [bytes.fromhex(h) for h in merkle.build_proof(leaves, 2)]
        self.assertFalse(merkle.verify_inclusion(merkle.leaf_hash(b"X"), 2, 5, proof, root))
        self.assertFalse(merkle.verify_inclusion(leaves[2], 3, 5, proof, root))

    def test_malformed_proof_returns_false_not_raise(self):
        leaves = [merkle.leaf_hash(b"a"), merkle.leaf_hash(b"b")]
        root = merkle.root_hash(leaves)
        self.assertFalse(merkle.verify_inclusion(leaves[0], 0, 2, [b"short"], root))
        self.assertFalse(merkle.verify_inclusion(leaves[0], 0, 0, [], root))


class StrictBase64Tests(unittest.TestCase):
    def test_canonical_values_pass(self):
        for v in ("YWJj", "YWI=", "YQ==", ""):
            if v == "":
                continue
            self.assertEqual(encoding.problems(v), [], v)

    def test_pad_bit_set_is_rejected(self):
        # 'AB==' decodes to the same byte as 'AA==' only if pad bits are ignored
        self.assertTrue(encoding.problems("AB=="))
        self.assertTrue(encoding.problems("AAB="))

    def test_unpadded_is_rejected(self):
        self.assertTrue(encoding.problems("YWI"))
        self.assertTrue(encoding.problems("YQ"))

    def test_not_base64_is_rejected(self):
        for v in ("not base64!", "YW Jj", "YWJj\n", "Y.W.J"):
            self.assertTrue(encoding.problems(v), v)

    def test_impossible_length_is_rejected(self):
        self.assertTrue(encoding.problems("YWJjZ"))


class MerkleCheckIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s13-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        shutil.copytree(BASE, self.pkg)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ids(self, rep):
        return [c["id"] for c in rep["checks"]]

    def test_no_merkle_file_means_no_s13_and_package_still_verifies(self):
        rep = verify(self.pkg)
        self.assertNotIn("S13", self._ids(rep))
        self.assertFalse(rep.get("failed_checks"))

    def test_honest_merkle_file_passes(self):
        ev_dir = os.path.join(self.pkg, "evidence")
        idx = json.load(open(os.path.join(ev_dir, "index.json"), encoding="utf-8"))
        entries = sorted(idx.get("entries", idx if isinstance(idx, list) else []),
                         key=lambda e: e.get("path", ""))
        leaves = []
        for e in entries:
            leaves.append(merkle.leaf_hash(open(os.path.join(ev_dir, e["path"]), "rb").read()))
        doc = {
            "algorithm": "rfc6962-sha256",
            "size": len(leaves),
            "root": merkle.root_hash(leaves).hex(),
            "proofs": [{"path": e["path"], "index": i,
                        "proof": merkle.build_proof(leaves, i)}
                       for i, e in enumerate(entries)],
        }
        json.dump(doc, open(os.path.join(ev_dir, "merkle.json"), "w", encoding="utf-8"))
        rep = verify(self.pkg)
        s13 = [c for c in rep["checks"] if c["id"] == "S13"]
        self.assertEqual(s13 and s13[0]["result"], "PASS", s13)

    def test_lying_merkle_root_fails(self):
        ev_dir = os.path.join(self.pkg, "evidence")
        json.dump({"algorithm": "rfc6962-sha256", "size": 2,
                   "root": "00" * 32, "proofs": []},
                  open(os.path.join(ev_dir, "merkle.json"), "w", encoding="utf-8"))
        rep = verify(self.pkg)
        s13 = [c for c in rep["checks"] if c["id"] == "S13"]
        self.assertEqual(s13 and s13[0]["result"], "FAIL", s13)


if __name__ == "__main__":
    unittest.main()
