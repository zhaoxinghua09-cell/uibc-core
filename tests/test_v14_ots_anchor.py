"""OpenTimestamps anchor: real submission, honest status.

What the fixture actually is, checked 2026-11-21 and corrected here: the `.ots`
is a real proof returned by `alice.btc.calendar.opentimestamps.org` on
2026-11-17, but its own first 32 bytes - the message the calendar timestamped -
are `f0087497…f120`, which is **not** the `4ad23d91…6e98` head that the RFC 3161
path timestamped and which `anchored_head.json` holds. So the two anchors do
**not** cover one digest, and until 2026-11-21 this file's docstring said they
did. The proof also has no standard container header, so the official `ots`
client refuses it ("is not a timestamp file").

The assertions are about what the proof actually says, not what we wish it said:

  * it contains a pending calendar attestation and zero Bitcoin block
    attestations, so the honest status is "pending", never "verified";
  * the head the TSA token covers and the message the OTS proof carries are two
    different digests, and `ots_container.binds` accepts no digest for the
    proof at all - the claim lives in assertions now, not in prose;
  * `--verify` refuses a proof that does not answer for the file it was handed,
    rather than walking it and printing the proof's own attestations;
  * a truncated proof yields no attestation rather than a claim.

The extra assertions went into two existing tests on purpose: a new test method
changes the suite count, and `docs/EVIDENCE-INDEX.md` embeds that count as a
measured fact.
"""

import hashlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

try:
    import opentimestamps  # noqa: F401
    HAVE_OTS = True
except ImportError:  # the verifier stays dependency-free; this test does not
    HAVE_OTS = False

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "anchor")
PROOF = os.path.join(FIX, "ots_head.ots")
HEAD = os.path.join(FIX, "anchored_head.json")
# The head the Free TSA token and anchored_head.json speak about.
EXPECTED = "4ad23d9153c33c77253b23e1f5938249cb6877de93eb7593dea26fa5f7fd6e98"
# The message the OTS proof really carries, read out of the proof itself.
OTS_ANCHORED = "f0087497e71943f5c1f308f010d39040ccaffbd6144475c1f9be6f88b808f120"


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
        """The TSA head, and - the part that used to be assumed - the proof's own."""
        from ots_container import binds, digest_of_file, is_standard

        with open(HEAD, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), EXPECTED)
        head_digest = digest_of_file(HEAD)

        with open(PROOF, "rb") as f:
            blob = f.read()
        self.assertEqual(blob[:32].hex(), OTS_ANCHORED,
                         "the OTS proof anchors a different message than it used to")
        self.assertNotEqual(blob[:32], head_digest,
                            "the OTS proof and the TSA token cover different bytes; no "
                            "document may say they cover one digest")
        self.assertFalse(is_standard(blob),
                         "the published proof has no standard header, which is why the "
                         "official client refuses it")
        self.assertFalse(binds(blob, head_digest),
                         "a bare tree binds to no digest, so it cannot be tied to the head")

    def test_proof_carries_a_pending_calendar_attestation(self):
        """And it is refused when handed a file it does not answer for."""
        import anchor_ots

        kinds = _inspect(PROOF)
        self.assertIn("PendingAttestation", kinds)
        with self.assertRaises(RuntimeError):
            anchor_ots.inspect(PROOF, HEAD)

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
