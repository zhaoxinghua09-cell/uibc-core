# -*- coding: utf-8 -*-
"""The block-header cross-check: arithmetic a stranger can repeat, offline.

The receipt under `docs/` records the bytes that were fetched on 2026-11-26 (80
header bytes for block 977449). Everything asserted here is derived from those
bytes with the standard library, so this test needs no network and no trust in
the servers that produced them:

  * sha256(sha256(header)) is the block hash;
  * the Merkle root lives at bytes 36..68, little-endian;
  * the digest that was fetched equals the OpenTimestamps attestation's message.

A byte flipped anywhere in the header has to break at least one of those, and
this test proves the checker notices instead of printing a green line.
"""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    import opentimestamps  # noqa: F401
    HAVE_OTS = True
except ImportError:
    HAVE_OTS = False

from tools import ots_block_crosscheck as cc  # noqa: E402

RECEIPT = os.path.join(ROOT, "docs", "anchor-ots-block-977449.json")
PROOF = os.path.join(ROOT, "tests", "fixtures", "anchor", "ots_head.ots")


def _receipt():
    with open(RECEIPT, encoding="utf-8") as f:
        return json.load(f)


class HeaderArithmeticTests(unittest.TestCase):
    def test_receipt_recomputes_from_its_own_bytes(self):
        doc, problems = cc.check_receipt(RECEIPT)
        self.assertEqual(problems, [], "the committed receipt must recompute cleanly")
        self.assertEqual(doc["verdict"], "HEADER_MATCHES_ATTESTATION")

    def test_header_hashes_to_the_block_hash(self):
        doc = _receipt()
        header = bytes.fromhex(doc["header_hex"])
        self.assertEqual(len(header), cc.HEADER_LEN)
        self.assertEqual(cc.display(cc.sha256d(header)), doc["header_sha256d"])
        self.assertEqual(doc["header_sha256d"], doc["sources"]["blockstream.info"]["block_hash"])

    def test_merkle_root_is_the_attestation_message(self):
        doc = _receipt()
        header = bytes.fromhex(doc["header_hex"])
        root_le = cc.merkle_root_of_header(header)
        self.assertEqual(root_le.hex(), doc["attestation_msgs_le"][0],
                         "attestation and header store the root in the same byte order")
        self.assertEqual(cc.display(root_le), doc["attestation_msgs"][0])

    def test_two_sources_agree(self):
        doc = _receipt()
        self.assertTrue(doc["sources_agree_on_hash"])
        self.assertTrue(doc["sources_agree_on_merkle_root"])
        self.assertEqual(sorted(doc["sources_answering"]),
                         ["blockchain.info", "blockstream.info"],
                         "one operator is one point of failure")

    def test_confirmation_depth_is_measured_not_assumed(self):
        doc = _receipt()
        tips = [v for v in doc["tip_heights"].values() if isinstance(v, int)]
        self.assertEqual(len(tips), 2, "both operators must answer with a tip height")
        self.assertEqual(doc["confirmations"], min(tips) - doc["height"])
        self.assertGreaterEqual(doc["confirmations"], 6,
                                "CTS recommends anchoring at depth >= 6; below that, "
                                "the claim would have to say so")

    def test_a_flipped_header_byte_is_caught(self):
        doc = _receipt()
        tampered = copy.deepcopy(doc)
        header = bytearray(bytes.fromhex(doc["header_hex"]))
        header[37] ^= 0x01  # inside the Merkle root
        tampered["header_hex"] = bytes(header).hex()
        tmp = os.path.join(os.path.dirname(RECEIPT), "_tampered.json")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(tampered, f)
        try:
            _doc, problems = cc.check_receipt(tmp)
        finally:
            os.remove(tmp)
        self.assertTrue(problems, "a tampered header must not recompute cleanly")
        self.assertIn("merkle root recomputed from header differs from the recorded one",
                      problems)

    def test_a_header_that_is_not_80_bytes_is_refused(self):
        with self.assertRaises(ValueError):
            cc.merkle_root_of_header(b"\x00" * 79)

    def test_receipt_and_proof_are_about_the_same_digest(self):
        if not HAVE_OTS:
            self.skipTest("opentimestamps not installed")
        doc = _receipt()
        atts = cc.block_attestations(PROOF)
        self.assertTrue(atts, "the fixture proof must carry block attestations")
        heights = sorted({h for h, _m in atts})
        self.assertEqual(heights, [doc["height"]])
        self.assertIn(doc["merkle_root_from_header"],
                      [cc.display(m) for _h, m in atts],
                      "the recorded header must be the block the proof names")


CHAIN = os.path.join(ROOT, "docs", "anchor-ots-chain-977449.json")


def _chain():
    if not os.path.isfile(CHAIN):
        return None
    with open(CHAIN, encoding="utf-8") as f:
        return json.load(f)


class ChainSegmentTests(unittest.TestCase):
    """Every header from the attested block up to the tip, re-derived offline."""

    def test_chain_receipt_recomputes_cleanly(self):
        if _chain() is None:
            self.skipTest("chain receipt not present")
        doc, problems = cc.check_chain_receipt(CHAIN)
        self.assertEqual(problems, [])
        self.assertEqual(doc["verdict"], "CHAIN_SEGMENT_VERIFIED")

    def test_segment_is_the_tip_window(self):
        doc = _chain()
        if doc is None:
            self.skipTest("chain receipt not present")
        self.assertEqual(len(doc["headers"]), doc["expected_length"])
        self.assertEqual(doc["headers"][-1]["height"], doc["height"] + 1,
                         "the window must start one block above the attested height")
        self.assertGreaterEqual(doc["expected_length"], 6,
                                "below the CTS floor the claim would have to say so")

    def test_every_header_meets_its_own_target(self):
        doc = _chain()
        if doc is None:
            self.skipTest("chain receipt not present")
        for item in doc["headers"]:
            ok, _target = cc.meets_target(bytes.fromhex(item["header_hex"]))
            self.assertTrue(ok, "block %s fails its own difficulty target" % item["height"])

    def test_bits_are_read_little_endian(self):
        doc = _chain()
        if doc is None:
            self.skipTest("chain receipt not present")
        header = bytes.fromhex(doc["headers"][0]["header_hex"])
        bits = cc.bits_of_header(header)
        self.assertEqual(bits >> 24, 0x17,
                         "mainnet difficulty bits start 0x17; a big-endian read gives "
                         "0x73 and every block looks invalid")
        self.assertGreater(cc.difficulty_target(bits).bit_length(), 160)

    def test_a_flipped_header_breaks_the_segment_check(self):
        doc = _chain()
        if doc is None:
            self.skipTest("chain receipt not present")
        tampered = copy.deepcopy(doc)
        header = bytearray(bytes.fromhex(tampered["headers"][-2]["header_hex"]))
        header[5] ^= 0x01  # inside prev-hash: breaks linkage and the block id
        tampered["headers"][-2]["header_hex"] = bytes(header).hex()
        tmp = os.path.join(os.path.dirname(CHAIN), "_tampered_chain.json")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(tampered, f)
        try:
            _doc, problems = cc.check_chain_receipt(tmp)
        finally:
            os.remove(tmp)
        self.assertTrue(problems)
        self.assertTrue(any("does not hash to its recorded id" in p or
                            "prev-hash" in p for p in problems),
                        "a byte flip must be named as a broken link or a broken id")


    def test_the_global_work_question_is_recorded_as_unanswered(self):
        """No node on this machine: the receipt must say so instead of implying it."""
        doc = _chain()
        if doc is None:
            self.skipTest("chain receipt not present")
        self.assertIn("node", doc)
        self.assertFalse(doc["node"]["checked"],
                         "no Bitcoin Core node was configured when this receipt was made")
        self.assertIn("most-work", doc["node"]["reason"],
                      "an unanswered question has to be named, not left blank")


