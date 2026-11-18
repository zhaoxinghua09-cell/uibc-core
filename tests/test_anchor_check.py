"""An anchor is only worth something when it arrives by a different route.

These tests build a publisher bundle, then attack it the way the forgery experiment
attacks packages - rewrite the evidence, repair every declaration, sign with a
stranger's key - and require that the anchored check refuses, while the package
checked against its own key does not.

The last test is the reason this file exists: a bundle whose anchor was taken
from inside the bundle must not be able to earn ANCHORED.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

from anchor_check import check  # noqa: E402
from composed_forgery import _resign  # noqa: E402
from uibc_core.signing import ed_generate_seed  # noqa: E402
from composed_forgery import _rewrite_and_repair as rewrite_and_repair  # noqa: E402
from make_release_bundle import DEMO_SEED, build  # noqa: E402


class TestAnchorCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        build_dir = os.path.join(cls.tmp, "bundle")
        build(build_dir, DEMO_SEED)
        cls.bundle = build_dir
        cls.pkg = os.path.join(build_dir, "package")
        cls.anchor = json.load(open(os.path.join(build_dir, "anchor.json"),
                                    encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_publishers_own_bundle_is_anchored(self):
        r = check(self.pkg, dict(self.anchor))
        self.assertEqual(r["verdict"], "ANCHORED")
        self.assertEqual(r["trust_level"], "anchored")
        self.assertEqual(r["reasons"], [])

    def test_a_wrong_head_in_the_anchor_is_refused(self):
        a = dict(self.anchor)
        a["checkpoint_head"] = "sha256:" + "0" * 63 + "1"
        r = check(self.pkg, a)
        self.assertEqual(r["verdict"], "FAILED")
        self.assertTrue(any("S9" in x for x in r["reasons"]))

    def test_a_wrong_pinned_key_is_refused(self):
        a = dict(self.anchor)
        # a real Ed25519 key that simply is not the signer's
        import base64
        from uibc_core.signing import ed_public_key
        a["pubkey_b64"] = base64.b64encode(
            ed_public_key(ed_generate_seed())).decode()
        r = check(self.pkg, a)
        self.assertEqual(r["verdict"], "FAILED")
        self.assertTrue(any("S6" in x for x in r["reasons"]), r["reasons"])

    def test_a_repaired_and_re_signed_forgery_fails_the_anchor(self):
        forged = os.path.join(self.tmp, "forged")
        shutil.copytree(self.pkg, forged)
        rewrite_and_repair(forged)
        _resign(forged, ed_generate_seed())
        r = check(forged, dict(self.anchor))
        self.assertEqual(r["verdict"], "FAILED")
        self.assertTrue(any("S6" in x for x in r["reasons"]),
                        r["reasons"])

    def test_the_forgery_alone_still_looks_clean(self):
        # The contrast that makes the anchor meaningful: without the anchor, the
        # same forged bytes verify. This is the forgery envelope's row C.
        forged = os.path.join(self.tmp, "forged2")
        shutil.copytree(self.pkg, forged)
        rewrite_and_repair(forged)
        _resign(forged, ed_generate_seed())
        from uibc_core.verify import verify
        v = verify(forged)
        self.assertEqual(v["result"], "PASS")
        self.assertEqual(v["trust_level"], "unanchored")

    def test_an_anchor_without_a_key_is_refused(self):
        a = dict(self.anchor)
        a.pop("pubkey_b64", None)
        r = check(self.pkg, a)
        self.assertEqual(r["verdict"], "FAILED")

    # --- the optional RFC 3161 block: an anchor without it pins a key and a
    # head but not a moment, and that difference has to be judged, not assumed.

    def _fixture_tsa(self, digest_hex, cabundle=True):
        import base64 as b64
        d = os.path.join(_REPO, "tests", "fixtures", "anchor")
        block = {"covers": "file", "data_sha256": digest_hex,
                 "token_b64": b64.b64encode(
                     open(os.path.join(d, "freetsa.tsr"), "rb").read()).decode()}
        if cabundle:
            block["cabundle_b64"] = b64.b64encode(
                open(os.path.join(d, "freetsa_ca.pem"), "rb").read()).decode()
        return block

    # the SHA-256 of tests/fixtures/anchor/anchored_head.json: the real FreeTSA
    # token was issued over these bytes on 2026-11-17T08:11:35Z
    ANCHORED_HEAD_SHA = ("4ad23d9153c33c77253b23e1f5938249cb6877de93eb7593dea2"
                         "6fa5f7fd6e98")

    def test_a_real_tsa_token_verifies_offline(self):
        a = dict(self.anchor)
        a["tsa"] = self._fixture_tsa(self.ANCHORED_HEAD_SHA)
        r = check(self.pkg, a)
        self.assertEqual(r["verdict"], "ANCHORED")
        self.assertTrue(r["tsa"]["ok"])
        self.assertEqual(r["tsa"]["binding"], "unbound")  # says what it proves
        self.assertTrue(r["tsa"]["gen_time"].startswith("2026-11-17"))

    def test_a_token_over_other_bytes_is_refused(self):
        a = dict(self.anchor)
        a["tsa"] = self._fixture_tsa("0" * 64)
        r = check(self.pkg, a)
        self.assertEqual(r["verdict"], "FAILED")
        self.assertFalse(r["tsa"]["ok"])

    def test_a_timestamp_without_a_ca_bundle_is_refused(self):
        a = dict(self.anchor)
        a["tsa"] = self._fixture_tsa(self.ANCHORED_HEAD_SHA, cabundle=False)
        r = check(self.pkg, a)
        self.assertEqual(r["verdict"], "FAILED")

    def test_the_wrong_cover_mode_is_refused(self):
        # the token covers a release-status file, not the four pinned values
        a = dict(self.anchor)
        block = self._fixture_tsa(self.ANCHORED_HEAD_SHA)
        block["covers"] = "anchor_digest"
        block.pop("data_sha256")
        a["tsa"] = block
        r = check(self.pkg, a)
        self.assertEqual(r["verdict"], "FAILED")
        self.assertEqual(r["tsa"]["binding"], "anchor_digest")


if __name__ == "__main__":
    unittest.main()
