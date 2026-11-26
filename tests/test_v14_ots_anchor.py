"""OpenTimestamps anchor: real submission, honest status, checked binding.

The `.ots` fixture is a real detached-timestamp proof returned by the three
public calendars on 2026-11-25 for the digest `4ad23d91…` - the same head that
Free TSA timestamped. Two anchors, one digest.

The assertions are about what the proof actually says, not what we wish it said:

  * it is a standard `.ots` container that the official client also reads
    (magic header, version, digest) - the 2026-11-17 fixture was a bare tree
    that `ots info` refused, so nothing in it was checkable by a stranger;
  * the digest it commits to equals the digest of `anchored_head.json`, so the
    proof is about this file and not some other byte string;
  * it contains pending calendar attestations from distinct calendars *and*
    three Bitcoin block attestations naming block 977449 (upgraded
    2026-11-26), so the honest status is `bitcoin_attested` - a block
    attestation in the proof, with the header itself not checked here;
  * a truncated proof yields no attestation rather than a claim.
"""

import hashlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    import opentimestamps  # noqa: F401
    HAVE_OTS = True
except ImportError:  # the verifier stays dependency-free; this test does not
    HAVE_OTS = False

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "anchor")
PROOF = os.path.join(FIX, "ots_head.ots")
HEAD = os.path.join(FIX, "anchored_head.json")
EXPECTED = "4ad23d9153c33c77253b23e1f5938249cb6877de93eb7593dea26fa5f7fd6e98"
#: the header the OpenTimestamps spec puts in front of every serialized proof
MAGIC = bytes(b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94")


def _attestations(proof_path):
    from opentimestamps.core.serialize import StreamDeserializationContext
    from opentimestamps.core.timestamp import DetachedTimestampFile

    with open(proof_path, "rb") as f:
        dtf = DetachedTimestampFile.deserialize(StreamDeserializationContext(f))
    out = []

    def walk(t):
        for att in t.attestations:
            out.append(att)
        for _op, child in t.ops.items():
            walk(child)

    walk(dtf.timestamp)
    return dtf.file_digest.hex(), out


@unittest.skipUnless(HAVE_OTS, "opentimestamps not installed; the verifier itself stays "
                                "dependency-free, so this proof check is skipped, not failed")
class OpenTimestampsTests(unittest.TestCase):
    def test_proof_fixture_exists(self):
        self.assertTrue(os.path.isfile(PROOF))

    def test_head_digest_is_the_documented_one(self):
        with open(HEAD, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), EXPECTED)

    def test_proof_is_a_standard_container(self):
        with open(PROOF, "rb") as f:
            blob = f.read()
        self.assertEqual(blob[:len(MAGIC)], MAGIC,
                         "a proof without the magic header is a bare tree: the official "
                         "client refuses it and nobody else can check it")

    def test_proof_commits_to_the_head_digest(self):
        digest, _atts = _attestations(PROOF)
        self.assertEqual(digest, EXPECTED,
                         "the proof must be about anchored_head.json, not another digest")

    def test_proof_carries_pending_calendar_attestations(self):
        _digest, atts = _attestations(PROOF)
        pending = [a for a in atts if type(a).__name__ == "PendingAttestation"]
        self.assertGreaterEqual(len(pending), 1)
        uris = {getattr(a, "uri", "") for a in pending}
        self.assertGreaterEqual(len(uris), 2,
                                "one calendar is one point of failure; ask several, and "
                                "say so instead of implying a single trustworthy one")

    def test_proof_carries_a_bitcoin_block_attestation(self):
        """Upgraded 2026-11-26: the proof now names a block, and names it exactly."""
        _digest, atts = _attestations(PROOF)
        blocks = [a for a in atts if type(a).__name__ == "BitcoinBlockHeaderAttestation"]
        self.assertGreaterEqual(len(blocks), 1,
                                "the upgrade landed; if this fails, the fixture was rolled back")
        heights = {getattr(a, "height", None) for a in blocks}
        self.assertEqual(heights, {977449},
                         "the block height is what the calendars returned on 2026-11-26")

    def test_tool_reports_bound_and_never_crosschecks_the_header(self):
        sys.path.insert(0, ROOT)
        from tools import anchor_ots

        doc = anchor_ots.verify(HEAD, PROOF)
        self.assertTrue(doc["bound"])
        self.assertTrue(doc["readable"])
        self.assertEqual(doc["bitcoin_block"], ["977449"] * 3,
                         "verify() must report the height of each block attestation, "
                         "not a blank string")
        self.assertGreaterEqual(doc["pending_calendar"], 1,
                                "calendars stay listed beside the block attestation")

    def test_truncated_proof_does_not_yield_an_attestation(self):
        with open(PROOF, "rb") as f:
            blob = f.read()
        tmp = os.path.join(os.path.dirname(PROOF), "_trunc.ots")
        with open(tmp, "wb") as f:
            f.write(blob[:20])
        try:
            _digest, atts = _attestations(tmp)
        except Exception:  # noqa: BLE001 - a broken proof may raise, which is fine
            atts = []
        finally:
            os.remove(tmp)
        self.assertEqual(atts, [])

    def test_the_2026_11_17_proof_is_kept_as_a_record_and_still_refused(self):
        """The old fixture was a bare tree; it is kept, byte for byte, to prove it was."""
        old = os.path.join(FIX, "ots_head_20261117_invalid.ots")
        self.assertTrue(os.path.isfile(old))
        with open(old, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(),
                             "9c22be2489a0fd5b2f956a390e7f89a250aa9e0cd7b4fe38d8f50f1236ae3066")
        sys.path.insert(0, ROOT)
        from tools import anchor_ots

        doc = anchor_ots.verify(HEAD, old)
        self.assertFalse(doc["readable"],
                         "a bare tree must be reported unreadable, not listed as pending")


if __name__ == "__main__":
    unittest.main()
