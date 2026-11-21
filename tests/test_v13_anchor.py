"""S15 anchor event resolution.

Each test maps to one class the AER-1 anchored corpus marks must-fail:
valid / missing-proof / bad-leaf-hash / bad-timestamp / bad-id-version /
unresolvable-anchor. The rule under test is behavioural: resolve or do not.
"""

import json
import os
import shutil
import tempfile
import unittest

from uibc_core import anchor, merkle
from uibc_core.verify import verify

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "fixtures", "clean.uibc")


def _setup(n=3):
    leaves = [merkle.leaf_hash(("e%d" % i).encode()) for i in range(n)]
    root = merkle.root_hash(leaves)
    return leaves, root


def _anchor(leaves, tree_root, index=1, **override):
    doc = {
        "id": "anchor-001",
        "version": 1,
        "leaf_hash": leaves[index].hex(),
        "anchored_at": "2026-11-17T08:00:00Z",
        "root": tree_root.hex(),
        "size": len(leaves),
        "index": index,
        "proof": merkle.build_proof(leaves, index),
    }
    doc.update(override)
    return doc


class AnchorResolveTests(unittest.TestCase):
    def test_valid_anchor_resolves(self):
        leaves, root = _setup()
        ok, probs = anchor.resolve(_anchor(leaves, root), root=root, leaves=leaves)
        self.assertTrue(ok, probs)

    def test_unresolvable_root_is_rejected(self):
        leaves, root = _setup()
        a = _anchor(leaves, root, root=(b"\x11" * 32).hex())
        ok, probs = anchor.resolve(a, root=root, leaves=leaves)
        self.assertFalse(ok)
        self.assertIn("not the root this package resolves to", probs[0])

    def test_missing_proof_is_rejected(self):
        leaves, root = _setup()
        ok, probs = anchor.resolve(_anchor(leaves, root, proof=[]), root=root)
        self.assertFalse(ok)
        self.assertTrue(any("proof" in p for p in probs))

    def test_bad_leaf_hash_is_rejected(self):
        leaves, root = _setup()
        ok, probs = anchor.resolve(_anchor(leaves, root, leaf_hash="XYZ"), root=root)
        self.assertFalse(ok)
        self.assertTrue(any("leaf_hash" in p for p in probs))

    def test_bad_timestamp_is_rejected(self):
        for ts in ("2026-11-17T08:00:00", "1900-02-29T00:00:00Z", "2026-06-30T23:59:60Z"):
            leaves, root = _setup()
            ok, probs = anchor.resolve(_anchor(leaves, root, anchored_at=ts), root=root)
            self.assertFalse(ok, ts)
            self.assertTrue(any("anchored_at" in p for p in probs), ts)

    def test_bad_id_version_is_rejected(self):
        leaves, root = _setup()
        ok, probs = anchor.resolve(_anchor(leaves, root, id="  ", version=0), root=root)
        self.assertFalse(ok)
        self.assertTrue(any("id" in p for p in probs))
        self.assertTrue(any("version" in p for p in probs))

    def test_wrong_index_is_rejected(self):
        leaves, root = _setup()
        # a valid index-1 anchor whose index field is relabelled 0: the proof and
        # the leaf belong to another position, so nothing should resolve
        relabelled = dict(_anchor(leaves, root, index=1), index=0)
        ok, probs = anchor.resolve(relabelled, root=root, leaves=leaves)
        self.assertFalse(ok)
        self.assertTrue(any("proof" in p or "index" in p or "leaf_hash" in p
                            for p in probs), probs)

    def test_hostile_input_never_raises(self):
        for bad in (None, {}, {"id": 1}, {"proof": "notalist"}, {"root": "zz"}):
            ok, probs = anchor.resolve(bad)
            self.assertFalse(ok)
            self.assertTrue(probs)

    def test_unsupported_resolver_is_not_counted(self):
        doc = {"resolver": "rekor", "anchors": []}
        probs, resolved, external = anchor.check_document(doc)
        self.assertTrue(probs)
        self.assertEqual(resolved, 0)
        self.assertEqual(external, 0)


class AnchorCheckIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s15-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        shutil.copytree(BASE, self.pkg)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, doc):
        ev = os.path.join(self.pkg, "evidence")
        with open(os.path.join(ev, "anchors.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f)

    def _s15(self, rep):
        for c in rep["checks"]:
            if c["id"] == "S15":
                return c
        return None

    def test_no_anchors_file_means_no_s15(self):
        self.assertIsNone(self._s15(verify(self.pkg)))

    def test_honest_anchor_package_passes(self):
        ev = os.path.join(self.pkg, "evidence")
        idx = json.load(open(os.path.join(ev, "index.json"), encoding="utf-8"))
        entries = sorted(idx.get("entries", []), key=lambda e: e.get("path", ""))
        leaves = [merkle.leaf_hash(open(os.path.join(ev, e["path"]), "rb").read())
                  for e in entries]
        root = merkle.root_hash(leaves)
        self._write({"resolver": "evidence-merkle",
                     "anchors": [_anchor(leaves, root, index=0)]})
        s15 = self._s15(verify(self.pkg))
        self.assertEqual(s15 and s15["result"], "PASS", s15)

    def test_lying_anchor_fails(self):
        self._write({"resolver": "evidence-merkle",
                     "anchors": [{"id": "a", "version": 1, "leaf_hash": "0" * 64,
                                  "anchored_at": "2026-11-17T08:00:00Z",
                                  "root": "0" * 64, "size": 2, "index": 0,
                                  "proof": ["0" * 64]}]})
        s15 = self._s15(verify(self.pkg))
        self.assertEqual(s15 and s15["result"], "FAIL", s15)


if __name__ == "__main__":
    unittest.main()
