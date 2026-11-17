"""Rekor anchoring: what we check, and what we refuse to claim.

Fixture = a real entry submitted to rekor.sigstore.dev on 2026-11-17 (log index
3944456508), plus the log's own public key so the log's signature over the entry
(SET) can be checked offline. The last two tests are the important ones: the
checkpoint and the inclusion proof are asserted to stay "not verified". Rekor's
checkpoint uses a key that is not the one published at /api/v1/log/publicKey,
and calling either of them verified would be the exact overclaim this project
exists to avoid.
"""

import base64
import copy
import importlib.util
import json
import os
import unittest

# A clean machine without the `verify` extra would otherwise show these as failures,
# which reads as "the project is broken" rather than "one optional path is untested".
# Skip loudly instead: `pip install -e .[verify]` runs them.
try:
    import cryptography  # noqa: F401
except ImportError:  # pragma: no cover
    raise unittest.SkipTest("cryptography not installed; run: pip install -e .[verify]")

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
        cls.doc = json.load(open(os.path.join(FIX, "rekor_entry.json"), encoding="utf-8"))
        with open(os.path.join(FIX, "rekor_head.json"), "rb") as f:
            cls.artifact = f.read()

    def log_pub(self):
        from cryptography.hazmat.primitives import serialization
        with open(os.path.join(FIX, "rekor_log_pub.pem"), "rb") as f:
            return serialization.load_pem_public_key(f.read())

    def test_entry_matches_the_artifact(self):
        ok, info, probs = self.mod.verify_entry(self.doc, self.artifact,
                                                log_pub=self.log_pub())
        self.assertTrue(ok, probs)
        self.assertEqual(info["log_index"], 3944456508)

    def test_log_signature_over_the_entry_verifies(self):
        ok, info, probs = self.mod.verify_entry(self.doc, self.artifact,
                                                log_pub=self.log_pub())
        self.assertTrue(ok, probs)
        self.assertTrue(info["set_verified"])

    def test_tampered_body_breaks_the_log_signature(self):
        tampered = copy.deepcopy(self.doc)
        payload = list(tampered.values())[0]
        raw = json.loads(base64.b64decode(payload["body"]).decode())
        raw["spec"]["data"]["hash"]["value"] = "00" * 32
        payload["body"] = base64.b64encode(json.dumps(raw).encode()).decode()
        ok, info, probs = self.mod.verify_entry(tampered, self.artifact,
                                                log_pub=self.log_pub())
        self.assertFalse(ok)
        self.assertFalse(info.get("set_verified"))
        self.assertTrue(any("signedEntryTimestamp" in p for p in probs), probs)

    def test_checkpoint_is_reported_but_not_claimed_verified(self):
        ok, info, probs = self.mod.verify_entry(self.doc, self.artifact,
                                                log_pub=self.log_pub())
        self.assertTrue(info["checkpoint"]["present"])
        self.assertFalse(info["checkpoint"]["verified"])

    def test_another_artifact_is_rejected(self):
        ok, info, probs = self.mod.verify_entry(self.doc, b"not the same file",
                                                log_pub=self.log_pub())
        self.assertFalse(ok)
        self.assertTrue(any("hashes" in p for p in probs), probs)

    def test_inclusion_proof_is_not_overclaimed(self):
        ok, info, probs = self.mod.verify_entry(self.doc, self.artifact,
                                                log_pub=self.log_pub())
        self.assertTrue(ok, probs)
        self.assertFalse(info["inclusion"]["verified"])

    def test_malformed_entry_never_raises(self):
        for bad in ({}, {"x": {}}, {"x": {"body": "!!!", "verification": {}}}):
            ok, info, probs = self.mod.verify_entry(bad, self.artifact,
                                                    log_pub=self.log_pub())
            self.assertFalse(ok)
            self.assertTrue(probs)


if __name__ == "__main__":
    unittest.main()
