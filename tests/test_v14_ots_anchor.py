"""OpenTimestamps anchor: real submission, honest status.

Two proofs live here, and the difference between them is the whole point:

  * `ots_head.ots` (2026-11-17) is the proof that was claimed to be "for the
    digest `4ad23d91…` - the same head that Free TSA timestamped. Two anchors,
    one digest". Read out of the proof itself on 2026-11-21, its first 32 bytes
    are `f0087497…f120`, which is **not** that head and is not the hash of any
    committed `tools/out/release_status.json`. It is also a bare tree with no
    standard header, so the official `ots` client refuses it ("is not a
    timestamp file").
  * `anchored_head.json.ots` (2026-11-21) is a re-stamp taken on the exact
    bytes the TSA token covers, written in the standard container. It binds,
    the official client can read it, and it still carries only a pending
    calendar attestation.

The assertions are about what the proofs actually say, not what we wish they said:

  * the 2026-11-17 proof carries a pending calendar attestation and zero
    Bitcoin block attestations, and it is refused when handed a file it does
    not answer for;
  * the 2026-11-21 proof binds to the TSA head, so "one digest, two anchors" is
    earned rather than assumed - and it too carries no block attestation;
  * a truncated proof yields no attestation rather than a claim.

The extra assertions went into existing test methods on purpose: a new method
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
RESTAMPED = os.path.join(FIX, "anchored_head.json.ots")
HEAD = os.path.join(FIX, "anchored_head.json")
# The head the Free TSA token and anchored_head.json speak about.
EXPECTED = "4ad23d9153c33c77253b23e1f5938249cb6877de93eb7593dea26fa5f7fd6e98"
# The message the 2026-11-17 proof really carries, read out of the proof itself.
OTS_ANCHORED = "f0087497e71943f5c1f308f010d39040ccaffbd6144475c1f9be6f88b808f120"


def _inspect(proof_path):
    """Walk a proof. A bare tree needs its message supplied; a standard container
    carries its own header, and passing blob[:32] to it parses the magic as a
    message - which reads as UnknownAttestation and hides what is really there."""
    from opentimestamps.core.serialize import BytesDeserializationContext
    from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp
    from ots_container import is_standard

    with open(proof_path, "rb") as f:
        blob = f.read()
    ctx = BytesDeserializationContext(blob)
    if is_standard(blob):
        ts = DetachedTimestampFile.deserialize(ctx).timestamp
    else:
        ts = Timestamp.deserialize(ctx, blob[:32])
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
                            "the 2026-11-17 proof and the TSA token cover different bytes; "
                            "no document may say they cover one digest")
        self.assertFalse(is_standard(blob),
                         "the 2026-11-17 proof has no standard header, which is why the "
                         "official client refuses it")
        self.assertFalse(binds(blob, head_digest),
                         "a bare tree binds to no digest, so it cannot be tied to the head")

        with open(RESTAMPED, "rb") as f:
            fresh = f.read()
        self.assertTrue(is_standard(fresh),
                        "the re-stamped proof must be readable by the official client, so "
                        "it needs the header")
        self.assertTrue(binds(fresh, head_digest),
                        "the re-stamped proof must answer for the TSA head; that is the "
                        "only way 'one digest, two anchors' is true")

    def test_proof_carries_a_pending_calendar_attestation(self):
        """Both proofs are pending, and the older one is refused for another file."""
        import anchor_ots

        kinds = _inspect(PROOF)
        self.assertIn("PendingAttestation", kinds)
        with self.assertRaises(RuntimeError):
            anchor_ots.inspect(PROOF, HEAD)

        fresh_kinds = _inspect(RESTAMPED)
        self.assertIn("PendingAttestation", fresh_kinds)
        self.assertNotIn("BitcoinBlockHeaderAttestation", fresh_kinds)
        anchor_ots.inspect(RESTAMPED, HEAD)  # must not raise: this one does bind

    def test_proof_does_not_claim_a_bitcoin_block(self):
        kinds = _inspect(PROOF)
        self.assertNotIn("BitcoinBlockHeaderAttestation", kinds,
                         "the fixture must not pretend a block attestation exists")

    def test_restamped_proof_names_several_calendars(self):
        """One calendar is one point of failure; the fixture says how many witnessed it."""
        from opentimestamps.core.serialize import BytesDeserializationContext
        from opentimestamps.core.timestamp import DetachedTimestampFile

        with open(RESTAMPED, "rb") as f:
            ctx = BytesDeserializationContext(f.read())
        dtf = DetachedTimestampFile.deserialize(ctx)
        uris = []

        def walk(t):
            for att in t.attestations:
                if type(att).__name__ == "PendingAttestation":
                    uris.append(getattr(att, "uri", ""))
            for _op, child in t.ops.items():
                walk(child)

        walk(dtf.timestamp)
        self.assertGreaterEqual(len(set(uris)), 2,
                                "the published proof must carry more than one calendar's "
                                "attestation, and must not imply a single trusted one")

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
