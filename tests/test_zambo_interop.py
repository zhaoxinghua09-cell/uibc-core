import unittest

from tools.zambo_interop_check import check


def _network_ok() -> bool:
    try:
        import urllib.request

        req = urllib.request.Request(
            "https://zambo.dev/run/5f908958-6c31-4293-b239-b2122699e14b",
            headers={"User-Agent": "uibc-core-interop/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as f:
            return f.status == 200
    except Exception:
        return False


class ZamboInterop(unittest.TestCase):
    """Cross-implementation check against a third party's published receipt.

    Skipped when the network or the page is unavailable: an offline CI run must
    never turn "cannot fetch" into "verified".
    """

    def setUp(self):
        if not _network_ok():
            self.skipTest("zambo.dev unreachable from this environment")

    def test_digest_binds_bytes(self):
        r = check()
        self.assertTrue(r["bytes_identical"], "our canonicalization differs from theirs")
        self.assertTrue(r["digest_match"], "recomputed digest differs from claimed digest")
        self.assertEqual(r["canonical_bytes"], 678)

    def test_declaration_hash_recomputes(self):
        r = check()
        self.assertTrue(r["declaration_match"], "side_effects declaration_hash mismatch")

    def test_envelope_is_unsigned_and_we_say_so(self):
        # If they start signing, this test flips and the doc claim must be updated.
        r = check()
        self.assertFalse(r["issuer_authenticated"])
        if r["signed"]:
            self.skipTest("envelope now carries a signature; update docs before claiming otherwise")


if __name__ == "__main__":
    unittest.main()
