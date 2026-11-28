"""Draft wire-shape receipts (rows 1 and 3 of the ASQAV crosswalk).

The two remaining partial rows are wire-format gaps, so the test target is the
draft's mandatory list, not our convenience:

  * a signed receipt verifies against a pinned key;
  * the same receipt with one byte of payload changed does NOT;
  * a receipt whose key is only inside the envelope does NOT verify (the
    verifier must not trust an embedded key);
  * a missing REQUIRED field is rejected;
  * a chain with a broken `previousReceiptHash` link is rejected;
  * a future-dated receipt is rejected;
  * an empty chain is rejected, not passed.
"""

import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.compliance import (GENESIS, build_receipt, canonical_action,  # noqa: E402
                                  receipt_digest, sign_receipt, verify_chain,
                                  verify_receipt)
from uibc_core.ed25519 import publickey  # noqa: E402

SEED = bytes(range(32))
PUB = publickey(SEED)
NOW = datetime(2026, 11, 17, 9, 0, 0, tzinfo=timezone.utc)


def _receipt(**kw):
    defaults = dict(issued_at="2026-11-17T08:58:00Z", issuer_id="did:web:example.eu",
                    policy_digest="sha256:" + "a" * 64,
                    payload_digest="sha256:" + "b" * 64)
    defaults.update(kw)
    action = {"tool": "read", "target": "x"}
    return sign_receipt(build_receipt(action, **defaults), SEED)


class ReceiptVerificationTests(unittest.TestCase):
    def test_signed_receipt_verifies_against_pinned_key(self):
        problems, digest = verify_receipt(_receipt(), pinned_pubkey=PUB, now=NOW)
        self.assertEqual(problems, [], problems)
        self.assertEqual(len(digest), 64)

    def test_tampered_payload_does_not_verify(self):
        r = _receipt()
        r["payload_digest"] = "sha256:" + "c" * 64
        problems, _ = verify_receipt(r, pinned_pubkey=PUB, now=NOW)
        self.assertTrue(any("does not verify" in p for p in problems), problems)

    def test_embedded_key_is_not_a_trust_anchor(self):
        problems, _ = verify_receipt(_receipt(), pinned_pubkey=None, now=NOW)
        self.assertTrue(any("pinned" in p for p in problems), problems)

    def test_other_key_is_rejected(self):
        other = publickey(bytes(range(1, 33)))
        problems, _ = verify_receipt(_receipt(), pinned_pubkey=other, now=NOW)
        self.assertTrue(problems)

    def test_missing_required_field_is_rejected(self):
        r = _receipt()
        del r["policy_digest"]
        problems, _ = verify_receipt(r, pinned_pubkey=PUB, now=NOW)
        self.assertIn("REQUIRED field 'policy_digest' is missing", problems)

    def test_future_dated_receipt_is_rejected(self):
        r = _receipt(issued_at="2026-11-17T15:00:00Z")
        problems, _ = verify_receipt(r, pinned_pubkey=PUB, now=NOW)
        self.assertTrue(any("in the future" in p for p in problems), problems)

    def test_action_ref_is_jcs_digest(self):
        r = build_receipt({"tool": "read", "target": "x"}, issued_at="x",
                          issuer_id="y", policy_digest="z", payload_digest="w")
        self.assertEqual(r["action_ref"], canonical_action({"tool": "read", "target": "x"}))


class ReceiptChainTests(unittest.TestCase):
    def _chain(self, n=3):
        out, prev = [], GENESIS
        for i in range(n):
            r = _receipt(issued_at="2026-11-17T08:5%d:00Z" % i)
            r["previousReceiptHash"] = prev
            r = sign_receipt({k: v for k, v in r.items() if k != "signatureObject"}, SEED)
            out.append(r)
            prev = receipt_digest(r)
        return out

    def test_valid_chain_passes(self):
        problems, checked = verify_chain(self._chain(), pinned_pubkey=PUB, now=NOW)
        self.assertEqual(problems, [], problems)
        self.assertEqual(checked, 3)

    def test_broken_link_is_rejected(self):
        chain = self._chain()
        body = {k: v for k, v in chain[2].items() if k != "signatureObject"}
        body["previousReceiptHash"] = "e" * 64
        chain[2] = sign_receipt(body, SEED)
        problems, _ = verify_chain(chain, pinned_pubkey=PUB, now=NOW)
        self.assertTrue(any("previousReceiptHash" in p for p in problems), problems)

    def test_empty_chain_is_rejected(self):
        problems, checked = verify_chain([], pinned_pubkey=PUB, now=NOW)
        self.assertTrue(problems)
        self.assertEqual(checked, 0)


if __name__ == "__main__":
    unittest.main()
