"""Two implementations, one publisher check.

`anchor_check.py` decides ANCHORED/FAILED with Python. `tools/verify-js/anchor.mjs`
decides the same question with node:crypto. Neither is derived from the other,
so agreement is evidence and disagreement is a bug - and the only way to know
which one you are getting is to run both on the same bundle.
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = "07" * 32


def _node():
    for name in ("node", "nodejs"):
        p = shutil.which(name)
        if p:
            return p
    return None


NODE = _node()


def _bundle(dst):
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "make_release_bundle.py"),
                        "--out", dst, "--seed-hex", SEED],
                       capture_output=True, text=True, cwd=REPO)
    if r.returncode != 0:
        raise AssertionError("build failed: " + r.stderr[-400:])


def _py(d):
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "anchor_check.py"), d],
                       capture_output=True, text=True, cwd=REPO)
    lines = [l for l in r.stdout.splitlines() if l.startswith("VERDICT")]
    return (lines[0].split(":")[1].strip() if lines else None), r.returncode


def _js(d):
    r = subprocess.run([NODE, os.path.join(REPO, "tools", "verify-js", "anchor.mjs"), d],
                       capture_output=True, text=True, cwd=REPO)
    lines = [l for l in r.stdout.splitlines() if l.startswith("VERDICT")]
    return (lines[0].split(":")[1].strip() if lines else None), r.returncode


@unittest.skipIf(NODE is None, "node is not installed")
class TestAnchorSecondImplementation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="anchor-js-")
        self.b = os.path.join(self.tmp, "b")
        _bundle(self.b)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_both_implementations_anchor_the_same_bundle(self):
        pv, prc = _py(self.b)
        jv, jrc = _js(self.b)
        self.assertEqual(pv, "ANCHORED")
        self.assertEqual(jv, "ANCHORED")
        self.assertEqual(prc, 0)
        self.assertEqual(jrc, 0)

    def test_a_tampered_head_is_refused_by_both(self):
        a = json.load(open(os.path.join(self.b, "anchor.json"), encoding="utf-8"))
        a["checkpoint_head"] = "sha256:" + "0" * 64
        json.dump(a, open(os.path.join(self.b, "anchor.json"), "w", encoding="utf-8"))
        pv, _ = _py(self.b)
        jv, _ = _js(self.b)
        self.assertEqual(pv, "FAILED")
        self.assertEqual(jv, "FAILED")

    def test_a_swapped_key_is_refused_by_both(self):
        a = json.load(open(os.path.join(self.b, "anchor.json"), encoding="utf-8"))
        a["pubkey_b64"] = base64.b64encode(b"\x11" * 32).decode("ascii")
        json.dump(a, open(os.path.join(self.b, "anchor.json"), "w", encoding="utf-8"))
        pv, _ = _py(self.b)
        jv, _ = _js(self.b)
        self.assertEqual(pv, "FAILED")
        self.assertEqual(jv, "FAILED")

    def test_an_anchor_that_is_not_there_anchors_nothing(self):
        os.remove(os.path.join(self.b, "anchor.json"))
        pv, prc = _py(self.b)
        jv, jrc = _js(self.b)
        self.assertNotEqual(prc, 0)
        self.assertNotEqual(jrc, 0)
        self.assertNotEqual(pv, "ANCHORED")
        self.assertIsNone(jv)  # refused before producing a verdict, on purpose


if __name__ == "__main__":
    unittest.main()
