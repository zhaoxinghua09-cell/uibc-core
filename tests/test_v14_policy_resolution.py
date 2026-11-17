"""S18 policy artefact resolution.

The clause being tested is draft-marques-asqav-compliance-receipts-01 section 8:
"Verifiers MUST reject Compliance Receipts whose policy_digest does not resolve
in the Audit Pack", with the digest defined as SHA-256 over the JCS encoding of
a retained artefact. The tests therefore assert the unhappy paths as hard as the
happy one:

  * a matching artefact + digest PASSes, and the receipt's declared digest
    resolves;
  * a wrong digest FAILs;
  * a missing artefact FAILs;
  * a non-JSON artefact FAILs (there is no JCS form to hash);
  * a receipt declaring a digest absent from the map FAILs (this is the
    rejection the draft actually demands);
  * a malformed digest (`sha256:xyz`) FAILs.
"""

import json
import os
import shutil
import tempfile
import unittest

from uibc_core.canonical import hash_obj
from uibc_core.verify import verify

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "fixtures", "clean.uibc")

POLICY = {"id": "policy/v1", "rules": [{"effect": "allow", "tool": "read"}]}


class PolicyResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s18-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        shutil.copytree(BASE, self.pkg)
        self.ev = os.path.join(self.pkg, "evidence")
        self.pdir = os.path.join(self.ev, "policy")
        os.makedirs(self.pdir, exist_ok=True)
        with open(os.path.join(self.pdir, "p.json"), "w", encoding="utf-8") as f:
            json.dump(POLICY, f, ensure_ascii=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _policies(self, digest=None, path="evidence/policy/p.json"):
        doc = {"policies": [{"digest": digest or "sha256:" + hash_obj(POLICY),
                             "path": path}]}
        with open(os.path.join(self.ev, "policies.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f)
        return doc

    def _chain_with_digest(self, digest):
        with open(os.path.join(self.ev, "chain.json"), "w", encoding="utf-8") as f:
            json.dump({"receipts": [
                {"envelope": {"policy_digest": digest},
                 "previous_receipt_hash": "0" * 64}]}, f)

    def _s18(self, rep):
        for c in rep["checks"]:
            if c["id"] == "S18":
                return c
        return None

    def test_no_policies_file_means_no_s18(self):
        self.assertIsNone(self._s18(verify(self.pkg)))

    def test_matching_artefact_passes(self):
        self._policies()
        s18 = self._s18(verify(self.pkg))
        self.assertEqual(s18 and s18["result"], "PASS", s18)
        self.assertIn("1 policy artefact", s18["detail"])

    def test_wrong_digest_fails(self):
        self._policies(digest="sha256:" + "0" * 64)
        s18 = self._s18(verify(self.pkg))
        self.assertEqual(s18 and s18["result"], "FAIL", s18)
        self.assertIn("hashes to", s18["detail"])

    def test_missing_artefact_fails(self):
        self._policies(path="evidence/policy/absent.json")
        s18 = self._s18(verify(self.pkg))
        self.assertEqual(s18 and s18["result"], "FAIL", s18)

    def test_non_json_artefact_fails(self):
        with open(os.path.join(self.pdir, "raw.json"), "w", encoding="utf-8") as f:
            f.write("effect: allow\n")
        self._policies(path="evidence/policy/raw.json")
        s18 = self._s18(verify(self.pkg))
        self.assertEqual(s18 and s18["result"], "FAIL", s18)

    def test_unresolved_receipt_digest_fails(self):
        digest = "sha256:" + hash_obj(POLICY)
        self._policies(digest=digest)
        self._chain_with_digest("sha256:" + "b" * 64)
        s18 = self._s18(verify(self.pkg))
        self.assertEqual(s18 and s18["result"], "FAIL", s18)
        self.assertIn("does not resolve", s18["detail"])

    def test_resolved_receipt_digest_passes(self):
        digest = "sha256:" + hash_obj(POLICY)
        self._policies(digest=digest)
        self._chain_with_digest(digest)
        s18 = self._s18(verify(self.pkg))
        self.assertEqual(s18 and s18["result"], "PASS", s18)

    def test_malformed_digest_fails(self):
        self._policies(digest="sha256:xyz")
        s18 = self._s18(verify(self.pkg))
        self.assertEqual(s18 and s18["result"], "FAIL", s18)


if __name__ == "__main__":
    unittest.main()
