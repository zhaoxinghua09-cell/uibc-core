"""Our capsule, judged by their reference implementation.

The interesting assertion here is not "our export is well formed" -- we could
test that against our own opinion forever. It is that `agent_action_capsule`,
written by someone else, accepts what our canonicalizer produced. Two JCS
implementations agreeing is exactly the kind of claim a document cannot make.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tools"))

import emit_aac_capsule as em  # noqa: E402

PKG = os.path.join(REPO, "fixtures", "clean.uibc")

try:
    from agent_action_capsule.verify import verify as aac_verify
except ImportError:  # pragma: no cover
    aac_verify = None

SKIP_LINE = "pip install agent-action-capsule"


class EmitAACCapsuleTests(unittest.TestCase):
    def setUp(self):
        self.cap = em.build_capsule(PKG)

    def test_the_capsule_id_is_ours_to_recompute(self):
        """Recomputation with our own JCS must agree with what we emitted."""
        self.assertEqual(em.capsule_id_of(self.cap), self.cap["capsule_id"])
        self.assertEqual(len(self.cap["capsule_id"]), 64)
        int(self.cap["capsule_id"], 16)  # hex, not base64

    def test_every_field_comes_off_the_package(self):
        with open(os.path.join(PKG, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(self.cap["action_id"], manifest["evidence_root"])
        self.assertEqual(self.cap["operator"], manifest["agent_id"])
        self.assertEqual(self.cap["timestamp"], manifest["created_at"])
        self.assertIn(manifest["agent_version"], self.cap["developer"])
        self.assertNotIn("signature", self.cap)

    def test_a_package_without_an_evidence_root_is_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("manifest.json", "identity.json"):
                with open(os.path.join(PKG, name), encoding="utf-8") as f:
                    data = json.load(f)
                if name == "manifest.json":
                    data.pop("evidence_root", None)
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
                    json.dump(data, f)
            with self.assertRaises(ValueError):
                em.build_capsule(tmp)

    @unittest.skipIf(aac_verify is None, SKIP_LINE)
    def test_their_verifier_accepts_our_capsule(self):
        """The claim that matters: someone else's code, our bytes."""
        result = aac_verify(self.cap)
        self.assertTrue(result.ok, [str(f) for f in result.findings or []])

    @unittest.skipIf(aac_verify is None, SKIP_LINE)
    def test_their_verifier_rejects_a_field_we_changed(self):
        """If we alter a covered field and keep the old id, they must notice."""
        tampered = dict(self.cap)
        tampered["action_id"] = "b" * 64
        result = aac_verify(tampered)
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
