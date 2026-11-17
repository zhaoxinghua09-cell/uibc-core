"""S16 external timestamp as a package-level check.

The token fixture is real (freetsa.org, 2026-11-17T08:11:35Z over the digest of
anchored_head.json). Two things matter here and both are asserted:

  * a package carrying a token that dates a file we ship PASSes, offline;
  * a token that dates a *different* digest, or a token whose bytes are not the
    declared ones, FAILs - so "we attached a token" cannot stand in for "the
    token says what we claim it says".
"""

import json
import os
import shutil
import tempfile
import unittest

# Without asn1crypto the verifier answers INCONCLUSIVE for every token, so the five
# assertions below would fail for a reason that has nothing to do with the logic
# they test. Skip, and say how to install it.
try:
    import asn1crypto  # noqa: F401
except ImportError:  # pragma: no cover
    raise unittest.SkipTest("asn1crypto not installed; run: pip install -e .[verify]")

from uibc_core.verify import verify

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "fixtures", "clean.uibc")
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "anchor")


class ExternalTimestampCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s16-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        shutil.copytree(BASE, self.pkg)
        self.ev = os.path.join(self.pkg, "evidence")
        self.tsa_dir = os.path.join(self.ev, "tsa")
        os.makedirs(self.tsa_dir, exist_ok=True)
        shutil.copy(os.path.join(FIX, "freetsa.tsr"), os.path.join(self.tsa_dir, "t.tsr"))
        shutil.copy(os.path.join(FIX, "freetsa_ca.pem"), os.path.join(self.tsa_dir, "ca.pem"))
        # the anchored file must be one the package actually ships
        shutil.copy(os.path.join(FIX, "anchored_head.json"),
                    os.path.join(self.ev, "anchored_head.json"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, doc):
        with open(os.path.join(self.ev, "external_anchor.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f)

    def _doc(self, **override):
        doc = {"scheme": "rfc3161",
               "tsa": "Free TSA",
               "tsr": "evidence/tsa/t.tsr",
               "cabundle": "evidence/tsa/ca.pem",
               "digest_of": "evidence/anchored_head.json"}
        doc.update(override)
        return doc

    def _s16(self, rep):
        for c in rep["checks"]:
            if c["id"] == "S16":
                return c
        return None

    def test_no_external_anchor_file_means_no_s16(self):
        self.assertIsNone(self._s16(verify(self.pkg)))

    def test_token_dating_a_shipped_file_passes(self):
        self._write(self._doc())
        s16 = self._s16(verify(self.pkg))
        self.assertEqual(s16 and s16["result"], "PASS", s16)
        self.assertIn("2026-11-17T08:11:35", s16["detail"])

    def test_token_dating_another_file_fails(self):
        other = os.path.join(self.ev, "unrelated.json")
        with open(other, "w", encoding="utf-8") as f:
            json.dump({"anything": 1}, f)
        self._write(self._doc(digest_of="evidence/unrelated.json"))
        s16 = self._s16(verify(self.pkg))
        self.assertEqual(s16 and s16["result"], "FAIL", s16)
        self.assertIn("messageImprint", s16["detail"])

    def test_declared_token_digest_must_match_bytes(self):
        self._write(self._doc(tsr_sha256="0" * 64))
        s16 = self._s16(verify(self.pkg))
        self.assertEqual(s16 and s16["result"], "FAIL", s16)

    def test_missing_token_file_fails(self):
        os.remove(os.path.join(self.tsa_dir, "t.tsr"))
        self._write(self._doc())
        s16 = self._s16(verify(self.pkg))
        self.assertEqual(s16 and s16["result"], "FAIL", s16)

    def test_missing_ca_bundle_fails(self):
        os.remove(os.path.join(self.tsa_dir, "ca.pem"))
        self._write(self._doc())
        s16 = self._s16(verify(self.pkg))
        self.assertEqual(s16 and s16["result"], "FAIL", s16)


if __name__ == "__main__":
    unittest.main()
