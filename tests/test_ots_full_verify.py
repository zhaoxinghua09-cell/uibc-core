# -*- coding: utf-8 -*-
"""One command, whole chain: file -> proof -> attestation -> header -> segment.

The joins are the point. Each receipt can be internally perfect and still be
about a different digest; these tests break one seam at a time and require the
command to stop at the right place instead of printing a green verdict.
"""
import json
import os
import shutil
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    import opentimestamps  # noqa: F401
    HAVE_OTS = True
except ImportError:
    HAVE_OTS = False

from tools import ots_full_verify as fv  # noqa: E402

HEAD = os.path.join(ROOT, "tests", "fixtures", "anchor", "anchored_head.json")
PROOF = os.path.join(ROOT, "tests", "fixtures", "anchor", "ots_head.ots")
BLOCK = os.path.join(ROOT, "docs", "anchor-ots-block-977449.json")
CHAIN = os.path.join(ROOT, "docs", "anchor-ots-chain-977449.json")


@unittest.skipUnless(HAVE_OTS, "opentimestamps not installed")
class FullVerifyTests(unittest.TestCase):
    def test_the_whole_chain_verifies(self):
        doc = fv.full_verify(HEAD, PROOF)
        self.assertEqual(doc["verdict"], "FULL_CHAIN_OF_EVIDENCE_VERIFIED", doc.get("problems"))
        self.assertTrue(doc["steps"]["proof_binds_file"]["ok"])
        self.assertTrue(doc["steps"]["header_receipt"]["root_in_attestation"])
        self.assertTrue(doc["steps"]["chain_receipt"]["starts_one_block_above"])

    def test_the_unanswered_question_is_listed_not_hidden(self):
        doc = fv.full_verify(HEAD, PROOF)
        self.assertFalse(doc["most_work_established"])
        self.assertTrue(any("most-work" in item for item in doc["unchecked"]),
                        "no node means the global question must appear as unchecked")

    def test_wrong_file_stops_at_the_proof(self):
        other = os.path.join(ROOT, "tools", "out", "release_status.json")
        if not os.path.isfile(other):
            self.skipTest("no second file to bind against")
        doc = fv.full_verify(other, PROOF)
        self.assertEqual(doc["verdict"], "STOPPED_AT_PROOF")

    def test_a_tampered_header_receipt_stops_at_the_header(self):
        tmp = os.path.join(ROOT, "docs", "_tampered_block.json")
        with open(BLOCK, encoding="utf-8") as f:
            doc = json.load(f)
        header = bytearray(bytes.fromhex(doc["header_hex"]))
        header[37] ^= 0x01
        doc["header_hex"] = bytes(header).hex()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        try:
            out = fv.full_verify(HEAD, PROOF, block_receipt=tmp)
        finally:
            os.remove(tmp)
        self.assertEqual(out["verdict"], "STOPPED_AT_HEADER")

    def test_a_receipt_for_another_block_stops_at_the_chain(self):
        tmp = os.path.join(ROOT, "docs", "_wrong_chain.json")
        shutil.copyfile(CHAIN, tmp)
        with open(tmp, encoding="utf-8") as f:
            doc = json.load(f)
        doc["block_hash"] = "00" * 32
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        try:
            out = fv.full_verify(HEAD, PROOF, chain_receipt=tmp)
        finally:
            os.remove(tmp)
        self.assertEqual(out["verdict"], "STOPPED_AT_CHAIN")


if __name__ == "__main__":
    unittest.main()
