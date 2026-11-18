#!/usr/bin/env python3
"""Tests for the AER-1 export path (tools/emit_aer1_receipts.py).

The independent-verdict half of this story needs the publisher's runner,
which is external and not vendored, so it is exercised by the tool
itself. What is pinned here is the part that must hold in CI: our own
emissions are accepted by our own verifier, the identifiers are
well-formed, and tampering is caught rather than waved through.
"""

import base64
import hashlib
import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


emit = _load("emit_aer1_receipts", "tools/emit_aer1_receipts.py")
verifier = _load("aer1_receipt_verifier", "tools/aer1_receipt_verifier.py")

PACKAGE = os.path.join(ROOT, "fixtures", "clean.uibc")


class EmitAer1Test(unittest.TestCase):
    def setUp(self):
        self.manifest, self.entries = emit.load_package(PACKAGE)
        self.receipts = [emit.build_receipt(self.manifest, entry, i, PACKAGE, PACKAGE)
                         for i, entry in enumerate(self.entries)]

    def test_one_receipt_per_evidence_entry(self):
        self.assertGreaterEqual(len(self.receipts), 2)
        self.assertEqual(len(self.receipts), len(self.entries))

    def test_our_verifier_accepts_our_output(self):
        for receipt in self.receipts:
            self.assertEqual(verifier.core_check(receipt), [])
            _, binding = verifier.version_and_binding(receipt)
            self.assertEqual(binding, [])

    def test_strict_metadata_mode_also_accepts(self):
        verifier.STRICT_METADATA = True
        try:
            for receipt in self.receipts:
                self.assertEqual(verifier.core_check(receipt), [])
        finally:
            verifier.STRICT_METADATA = False

    def test_identifiers_are_minted_uuid4(self):
        for receipt in self.receipts:
            self.assertTrue(verifier.STRICT_UUID_RE.match(receipt["id"]),
                            receipt["id"])
            self.assertNotEqual(receipt["id"], verifier.NIL_UUID)

    def test_output_hash_is_the_digest_of_the_emitted_bytes(self):
        for receipt in self.receipts:
            raw = base64.b64decode(receipt["canonical_bytes"], validate=True)
            self.assertEqual(receipt["output_hash"],
                             "sha256:" + hashlib.sha256(raw).hexdigest())

    def test_metadata_hash_recomputes(self):
        for receipt in self.receipts:
            self.assertEqual(receipt["metadata_hash"], verifier.metadata_digest(receipt))

    def test_tampered_output_hash_is_rejected(self):
        receipt = dict(self.receipts[0])
        receipt["output_hash"] = "sha256:" + "0" * 64
        self.assertTrue(verifier.core_check(receipt))

    def test_relabelled_provenance_is_rejected_by_binding(self):
        receipt = dict(self.receipts[0])
        receipt["provenance_class"] = "EXECUTED BY US"
        _, binding = verifier.version_and_binding(receipt)
        self.assertTrue(binding)

    def test_flipped_payload_byte_is_rejected(self):
        receipt = dict(self.receipts[0])
        raw = bytearray(base64.b64decode(receipt["canonical_bytes"], validate=True))
        raw[0] ^= 0x01
        receipt["canonical_bytes"] = base64.b64encode(bytes(raw)).decode("ascii")
        self.assertTrue(verifier.core_check(receipt))

    def test_impossible_date_is_rejected(self):
        receipt = dict(self.receipts[0])
        receipt["created_at"] = "2026-02-30T09:00:00.000Z"
        self.assertTrue(verifier.core_check(receipt))

    def test_payload_states_its_own_schema_and_claims(self):
        for receipt in self.receipts:
            payload = json.loads(base64.b64decode(receipt["canonical_bytes"],
                                                  validate=True).decode("utf-8"))
            self.assertEqual(payload["receipt_schema_version"],
                             receipt["receipt_schema_version"])
            self.assertEqual(payload["issuer_claims"]["provenance_class"],
                             receipt["provenance_class"])


if __name__ == "__main__":
    unittest.main()
