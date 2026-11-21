"""Interop matrix, executed: what our verifier does with three peer shapes.

The samples here are **synthetic**, built from each project's published field
names (agent-receipts' flat receipt, a DSSE envelope in the NovaFabric style, and
a hash-chained Vaara-style trail record). They are not captures of those tools
running, so the assertions are about our verifier's *behaviour and reasons*, not
about those products' correctness:

  * each peer shape is rejected;
  * the rejection names the missing ASQAV-required fields, so a reader can see
    exactly why the shapes do not interoperate;
  * a receipt that is ASQAV-shaped but signed by a key we do not pin is rejected
    for the trust reason, proving the rejects are not a blanket "unknown input".

`docs/INTEROP-MATRIX.md` records the same finding in prose; this file keeps it
from drifting.
"""

import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.compliance import verify_receipt, verify_chain  # noqa: E402
from uibc_core.compliance import build_receipt, sign_receipt  # noqa: E402
from uibc_core.ed25519 import publickey  # noqa: E402

SEED = bytes(range(32))
PUB = publickey(SEED)
NOW = datetime(2026, 11, 17, 9, 0, 0, tzinfo=timezone.utc)


def agent_receipts_shape():
    """As published on npm (v0.1 receipt): flat, per-tool-call, sig.value."""
    return {
        "v": "0.1",
        "id": "rcpt_01HQX7K9V3M2X8N5P0Q7R2T4W6",
        "ts": "2026-05-19T14:32:11.234Z",
        "agent": {"framework": "claude-code", "model": "claude-sonnet-4"},
        "principal": {"type": "user", "id": "user@example.dev"},
        "action": {"kind": "tool_call", "tool": "filesystem.write_file",
                   "inputs": {"disclosure": "hash", "hash": "sha256:" + "a" * 64},
                   "outputs": {"disclosure": "hash", "hash": "sha256:" + "b" * 64},
                   "duration_ms": 47},
        "sig": {"key_id": "key_2026_05", "alg": "ed25519", "value": "MEUCIQDk6"},
    }


def dsse_shape():
    """DSSE envelope in the NovaFabric / in-toto style."""
    return {
        "payloadType": "application/vnd.in-toto+json",
        "payload": "eyJfdHlwZSI6InJ1bi1jYXBzdWxlIn0=",
        "signatures": [{"keyid": "nova:1B5qkP", "sig": "MEUCIQ..."}],
    }


def vaara_shape():
    """Hash-chained trail record, export-signed."""
    return {
        "trail_id": "tr_01",
        "seq": 7,
        "prev_hash": "c" * 64,
        "record": {"tool": "write", "decision": "allow", "risk": 0.2},
        "export_sig": "MEYCIQ...",
    }


class InteropMatrixTests(unittest.TestCase):
    def test_agent_receipts_shape_is_rejected_with_reasons(self):
        problems, digest = verify_receipt(agent_receipts_shape(), pinned_pubkey=PUB, now=NOW)
        self.assertIsNone(digest)
        joined = " | ".join(problems)
        for field in ("type", "issuer_id", "action_ref", "policy_digest",
                      "payload_digest", "previousReceiptHash"):
            self.assertIn("'%s'" % field, joined)

    def test_dsse_shape_is_rejected(self):
        problems, _ = verify_receipt(dsse_shape(), pinned_pubkey=PUB, now=NOW)
        self.assertTrue(problems)
        self.assertIn("REQUIRED field 'type' is missing", problems[0])

    def test_vaara_shape_is_rejected(self):
        problems, _ = verify_receipt(vaara_shape(), pinned_pubkey=PUB, now=NOW)
        self.assertTrue(problems)

    def test_our_own_shape_is_the_only_one_accepted(self):
        good = sign_receipt(
            build_receipt({"tool": "read", "target": "x"},
                          issued_at="2026-11-17T08:58:00Z",
                          issuer_id="did:web:example.eu",
                          policy_digest="sha256:" + "a" * 64,
                          payload_digest="sha256:" + "b" * 64),
            SEED)
        problems, digest = verify_receipt(good, pinned_pubkey=PUB, now=NOW)
        self.assertEqual(problems, [])
        self.assertEqual(len(digest), 64)

    def test_chain_of_peer_shapes_is_rejected_not_crashed(self):
        chain = [agent_receipts_shape(), dsse_shape(), vaara_shape()]
        problems, checked = verify_chain(chain, pinned_pubkey=PUB, now=NOW)
        self.assertTrue(problems)
        self.assertEqual(checked, 0)

    def test_declared_algorithm_must_be_ed25519(self):
        r = sign_receipt(build_receipt({"tool": "read"}, issued_at="2026-11-17T08:58:00Z",
                                       issuer_id="did:web:x", policy_digest="sha256:" + "a" * 64,
                                       payload_digest="sha256:" + "b" * 64), SEED)
        r["signatureObject"]["alg"] = "ES256"
        problems, _ = verify_receipt(r, pinned_pubkey=PUB, now=NOW)
        self.assertTrue(any("expected 'Ed25519'" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
