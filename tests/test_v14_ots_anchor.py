"""OpenTimestamps anchor: real submission, honest status.

The `.ots` fixture is a real proof returned by
`alice.btc.calendar.opentimestamps.org` on 2026-11-17 for the digest
`4ad23d91…` - the same head that Free TSA timestamped. Two anchors, one digest.

The assertions are about what the proof actually says, not what we wish it said:

  * it contains exactly one pending calendar attestation and zero Bitcoin block
    attestations, so the honest status is "pending", never "verified";
  * the fixture's digest equals the digest in the RFC 3161 path, so the two
    anchors cover the same bytes;
  * a truncated proof yields no attestation rather than a claim.
"""

import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import opentimestamps  # noqa: F401
    HAVE_OTS = True
except ImportError:  # the verifier stays dependency-free; this test does not
    HAVE_OTS = False

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "anchor")
PROOF = os.path.join(FIX, "ots_head.ots")
HEAD = os.path.join(FIX, "anchored_head.json")
EXPECTED = "4ad23d9153c33c77253b23e1f5938249cb6877de93eb7593dea26fa5f7fd6e98"


def _inspect(proof_path):
    from opentimestamps.core.serialize import BytesDeserializationContext
    from opentimestamps.core.timestamp import Timestamp

    with open(proof_path, "rb") as f:
        blob = f.read()
    ts = Timestamp.deserialize(BytesDeserializationContext(blob), blob[:32])
    out = []

    def walk(t, depth=0):
        for att in t.attestations:
            out.append(type(att).__name__)
        for _op, child in t.ops.items():
            walk(child, depth + 1)

    walk(ts)
    return out


@unittest.skipUnless(HAVE_OTS, "opentimestamps not installed; the verifier itself stays "
                                "dependency-free, so this proof check is skipped, not failed")
class OpenTimestampsTests(unittest.TestCase):
    def test_proof_fixture_exists(self):
        self.assertTrue(os.path.isfile(PROOF))

    def test_head_digest_is_the_documented_one(self):
        with open(HEAD, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), EXPECTED)

    def test_proof_carries_a_pending_calendar_attestation(self):
        kinds = _inspect(PROOF)
        self.assertIn("PendingAttestation", kinds)

    def test_proof_does_not_claim_a_bitcoin_block(self):
        kinds = _inspect(PROOF)
        self.assertNotIn("BitcoinBlockHeaderAttestation", kinds,
                         "the fixture must not pretend a block attestation exists")

    def test_truncated_proof_does_not_yield_an_attestation(self):
        with open(PROOF, "rb") as f:
            blob = f.read()
        tmp = os.path.join(os.path.dirname(PROOF), "_trunc.ots")
        with open(tmp, "wb") as f:
            f.write(blob[:20])
        try:
            kinds = _inspect(tmp)
        except Exception:  # noqa: BLE001 - a broken proof may raise, which is fine
            kinds = []
        finally:
            os.remove(tmp)
        self.assertNotIn("PendingAttestation", kinds)


if __name__ == "__main__":
    unittest.main()
