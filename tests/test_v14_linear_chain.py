"""S17 linear receipt chain.

The point of this check is the one a Merkle tree cannot answer: is record N the
successor of record N-1? `draft-marques-asqav-compliance-receipts-01` section
4.3 makes `previousReceiptHash` mandatory and section 8 makes the verifier
recompute it, so the tests below are written against that clause rather than
against our own convenience:

  * a correctly linked chain PASSes;
  * a non-zero genesis FAILs (an appended chain may not invent a predecessor);
  * editing a middle envelope FAILs (the successor's link no longer matches);
  * dropping the first receipt FAILs (the new first carries a non-zero link);
  * a re-ordered pair FAILs;
  * an unjudgeable envelope (Float, which JCS cannot encode) FAILs rather than
    passing silently.
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
GENESIS = "0" * 64


class LinearChainCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s17-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        shutil.copytree(BASE, self.pkg)
        self.ev = os.path.join(self.pkg, "evidence")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _chain(self, n=3):
        receipts = []
        prev = GENESIS
        for i in range(n):
            env = {"type": "protectmcp:decision",
                   "issued_at": "2026-11-17T08:0%d:00Z" % i,
                   "issuer_id": "did:web:example.eu",
                   "action_ref": "sha256:" + ("%064x" % (i + 1))}
            receipts.append({"envelope": env, "previous_receipt_hash": prev})
            prev = hash_obj(env)
        return {"schema": "uibc-core/chain@1", "receipts": receipts}

    def _write(self, doc):
        with open(os.path.join(self.ev, "chain.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False)

    def _s17(self, rep):
        for c in rep["checks"]:
            if c["id"] == "S17":
                return c
        return None

    def test_no_chain_file_means_no_s17(self):
        self.assertIsNone(self._s17(verify(self.pkg)))

    def test_linked_chain_passes(self):
        self._write(self._chain())
        s17 = self._s17(verify(self.pkg))
        self.assertEqual(s17 and s17["result"], "PASS", s17)
        self.assertIn("3 receipt(s)", s17["detail"])

    def test_nonzero_genesis_fails(self):
        doc = self._chain()
        doc["receipts"][0]["previous_receipt_hash"] = "a" * 64
        self._write(doc)
        s17 = self._s17(verify(self.pkg))
        self.assertEqual(s17 and s17["result"], "FAIL", s17)
        self.assertIn("64 zeros", s17["detail"])

    def test_edited_middle_envelope_fails(self):
        doc = self._chain()
        doc["receipts"][1]["envelope"]["issuer_id"] = "did:web:attacker.eu"
        self._write(doc)
        s17 = self._s17(verify(self.pkg))
        self.assertEqual(s17 and s17["result"], "FAIL", s17)
        self.assertIn("predecessor", s17["detail"])

    def test_dropped_first_receipt_fails(self):
        doc = self._chain()
        doc["receipts"].pop(0)
        self._write(doc)
        s17 = self._s17(verify(self.pkg))
        self.assertEqual(s17 and s17["result"], "FAIL", s17)

    def test_reordered_pair_fails(self):
        doc = self._chain()
        doc["receipts"][1], doc["receipts"][2] = doc["receipts"][2], doc["receipts"][1]
        self._write(doc)
        s17 = self._s17(verify(self.pkg))
        self.assertEqual(s17 and s17["result"], "FAIL", s17)

    def test_unjudgeable_envelope_fails(self):
        # A chain document arrives as JSON, so this path is only reachable
        # through the library API - but it must still FAIL rather than claim
        # a link it cannot compute. `bytes` is not a JCS scalar.
        from uibc_core.chain import check_chain
        problems, checked = check_chain({"receipts": [
            {"envelope": {"blob": b"xx"}, "previous_receipt_hash": GENESIS}]})
        self.assertTrue(problems)
        self.assertEqual(checked, 0)

    def test_empty_chain_fails(self):
        self._write({"schema": "uibc-core/chain@1", "receipts": []})
        s17 = self._s17(verify(self.pkg))
        self.assertEqual(s17 and s17["result"], "FAIL", s17)


if __name__ == "__main__":
    unittest.main()
