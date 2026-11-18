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


if __name__ == "__main__":
    unittest.main()
