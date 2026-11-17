"""S16 external anchor: RFC 3161 timestamp, verified offline.

The fixture is a real token from freetsa.org taken 2026-11-17T08:11:35Z over the
digest of `anchored_head.json`. Keeping a real token in the repo is the point: the
test proves the verifier works on bytes we did not generate, not on a mock we
designed to pass.
"""

import hashlib
import importlib.util
import json
import os
import unittest

# Parsing an RFC 3161 token needs asn1crypto. Without it the tool answers
# "asn1crypto is unavailable" and this suite would report failures that are really
# a missing optional dependency; skip with the install line instead.
try:
    import asn1crypto  # noqa: F401
except ImportError:  # pragma: no cover
    raise unittest.SkipTest("asn1crypto not installed; run: pip install -e .[verify]")

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "tools", "anchor_tsa.py")
FIX = os.path.join(HERE, "fixtures", "anchor")


def _load_tool():
    spec = importlib.util.spec_from_file_location("anchor_tsa", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AnchorToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_tool()

    def _digest(self):
        with open(os.path.join(FIX, "anchored_head.json"), "rb") as f:
            return hashlib.sha256(f.read()).digest()

    def test_request_is_der_and_carries_our_digest(self):
        req = self.mod.build_request(self._digest())
        self.assertTrue(req.startswith(b"\x30"), "TimeStampReq must be a DER SEQUENCE")
        self.assertIn(self._digest(), req)   # messageImprint is the raw digest

    def test_real_token_parses_with_gen_time(self):
        body = open(os.path.join(FIX, "freetsa.tsr"), "rb").read()
        ok, info, probs = self.mod.parse_response(body)
        self.assertTrue(ok, probs)
        self.assertTrue(info["gen_time"].startswith("2026-11-17T08:11:35"))
        self.assertEqual(info["digest_hex"], self._digest().hex())
        self.assertEqual(info["tsa"]["organization_name"], "Free TSA")

    def test_real_token_verifies_offline(self):
        body = open(os.path.join(FIX, "freetsa.tsr"), "rb").read()
        ca = open(os.path.join(FIX, "freetsa_ca.pem"), "rb").read()
        ok, info, probs = self.mod.verify_token(body, self._digest(), ca)
        self.assertTrue(ok, probs)
        self.assertTrue(info.get("signature_verified"))

    def test_token_about_another_digest_is_rejected(self):
        body = open(os.path.join(FIX, "freetsa.tsr"), "rb").read()
        ca = open(os.path.join(FIX, "freetsa_ca.pem"), "rb").read()
        ok, info, probs = self.mod.verify_token(body, hashlib.sha256(b"other").digest(), ca)
        self.assertFalse(ok)
        self.assertTrue(any("messageImprint" in p for p in probs), probs)

    def test_garbage_token_never_raises(self):
        ca = open(os.path.join(FIX, "freetsa_ca.pem"), "rb").read()
        for body in (b"", b"not der", b"\x30\x00"):
            ok, info, probs = self.mod.verify_token(body, self._digest(), ca)
            self.assertFalse(ok)
            self.assertTrue(probs)

    def test_unknown_ca_means_not_verified(self):
        body = open(os.path.join(FIX, "freetsa.tsr"), "rb").read()
        ok, info, probs = self.mod.verify_token(body, self._digest(), b"")
        self.assertFalse(ok)
        self.assertTrue(any("CA" in p or "chains" in p for p in probs), probs)


if __name__ == "__main__":
    unittest.main()
