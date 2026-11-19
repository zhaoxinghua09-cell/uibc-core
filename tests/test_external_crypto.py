"""The third-party cross-check must keep agreeing — and must keep being able to
disagree.

`uibc_core/ed25519.py` is a pure-Python implementation. Our verifier using it
to verify our own signatures is self-consistent even if the implementation
were wrong. These tests hold the implementation to a third-party library
(`cryptography`, OpenSSL backend) on the same fact, and require the negative
probe to be refused — otherwise the verification could be passing while doing
nothing.
"""

import os
import sys
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

TOOLS = os.path.join(REPO, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

try:
    import external_crypto_check as ecc
except Exception:  # pragma: no cover
    ecc = None


@unittest.skipUnless(ecc is not None and ecc.HAVE_CRYPTOGRAPHY,
                     "cryptography is not installed; no third party to compare against")
class TestThirdPartyCryptoAgreement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        import zipfile
        cls._tmp = tempfile.mkdtemp(prefix="uibc-extcrypto-test-")
        with zipfile.ZipFile(ecc._ZIP) as z:
            z.extractall(cls._tmp)
        cls._root = os.path.join(cls._tmp, "cases")

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_every_ed25519_package_agrees(self):
        rows, skipped_hmac = ecc.run(self._root)
        self.assertGreater(len(rows), 0, "no Ed25519 package found to compare on")
        disagree = [r for r in rows if not r["agree"]]
        self.assertEqual(disagree, [], "third party and our implementation disagree: %s" % disagree)
        self.assertGreater(skipped_hmac, 0, "HMAC packages should be counted as skipped, not hidden")

    def test_the_negative_probe_is_refused(self):
        probe = ecc.probe(self._root)
        self.assertIsNotNone(probe)
        self.assertTrue(probe["tampered_refused"],
                        "a one-byte edit was accepted: the verification is not checking content")


class TestTheScriptSaysWhatItDoesNotCheck(unittest.TestCase):
    def test_limits_are_stated_in_the_source(self):
        path = os.path.join(REPO, "tools", "external_crypto_check.py")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("NOT CHECKED HERE", src)
        self.assertIn("RFC 8785", src)


if __name__ == "__main__":
    unittest.main()
