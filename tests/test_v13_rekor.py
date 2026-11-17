"""Rekor anchoring: what we check, and what we refuse to claim.

Fixture = a real entry submitted to rekor.sigstore.dev on 2026-11-17 (log index
3944456508). The last test is the important one: we assert the tool reports its
inclusion proof as NOT independently verified. Rekor's proof needs the log's
signed checkpoint, and calling that "verified" would be the exact overclaim this
project exists to avoid.
"""

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "tools", "anchor_rekor.py")
FIX = os.path.join(HERE, "fixtures", "anchor")


def _load():
    spec = importlib.util.spec_from_file_location("anchor_rekor", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RekorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load()
        import json
        cls.doc = json.load(open(os.path.join(FIX, "rekor_entry.json"), encoding="utf-8"))
        with open(os.path.join(FIX, "rekor_head.json"), "rb") as f:
            cls.artifact = f.read()

    def test_entry_matches_the_artifact(self):
        ok, info, probs = self.mod.verify_entry(self.doc, self.artifact)
        self.assertTrue(ok, probs)
        self.assertEqual(info["log_index"], 3944456508)

    def test_another_artifact_is_rejected(self):
        ok, info, probs = self.mod.verify_entry(self.doc, b"not the same file")
        self.assertFalse(ok)
        self.assertTrue(any("hashes" in p for p in probs), probs)

    def test_inclusion_proof_is_not_overclaimed(self):
        ok, info, probs = self.mod.verify_entry(self.doc, self.artifact)
        self.assertTrue(ok, probs)
        self.assertFalse(info["inclusion"]["verified"])

    def test_malformed_entry_never_raises(self):
        for bad in ({}, {"x": {}}, {"x": {"body": "!!!", "verification": {}}}):
            ok, info, probs = self.mod.verify_entry(bad, self.artifact)
            self.assertFalse(ok)
            self.assertTrue(probs)


if __name__ == "__main__":
    unittest.main()
