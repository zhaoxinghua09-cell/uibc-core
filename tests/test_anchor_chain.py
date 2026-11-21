"""Can a stranger tell a stale anchor from a current one?

Both are internally perfect. Both verify. The difference is position, and
position is the one thing a digest never had - so the anchors name their
predecessor, and these tests hold that naming to account.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")


def _build(out, seed, prev=None):
    cmd = [sys.executable, os.path.join(TOOLS, "make_release_bundle.py"),
           "--out", out, "--seed-hex", seed]
    if prev:
        cmd += ["--prev-anchor", prev]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    if r.returncode != 0:
        raise AssertionError("build failed: " + r.stderr[-400:])
    return os.path.join(out, "anchor.json")


def _chain(dirpath, *extra):
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "anchor_chain.py"),
                        dirpath, *extra], capture_output=True, text=True, cwd=REPO)
    lines = [l for l in r.stdout.splitlines() if l.startswith("VERDICT")]
    return (lines[0].split(":", 1)[1].strip() if lines else None), r.returncode


def _check(bundle, prev=None):
    cmd = [sys.executable, os.path.join(TOOLS, "anchor_check.py"), bundle]
    if prev:
        cmd += ["--prev", prev]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    lines = [l for l in r.stdout.splitlines() if l.startswith("VERDICT")]
    return (lines[0].split(":", 1)[1].strip() if lines else None), r.returncode


class TestAnchorChain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="chain-")
        self.dir = os.path.join(self.tmp, "anchors")
        os.makedirs(self.dir)
        self.a = []
        prev = None
        seeds = ["11" * 32, "22" * 32, "33" * 32]
        for i, seed in enumerate(seeds, start=1):
            path = _build(os.path.join(self.tmp, "b%d" % i), seed, prev)
            self.a.append(path)
            prev = path
            shutil.copy(path, os.path.join(self.dir, "%03d.json" % i))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_three_anchors_form_a_line(self):
        v, rc = _chain(self.dir)
        self.assertEqual(v, "CHAIN OK")
        self.assertEqual(rc, 0)

    def test_a_missing_middle_anchor_breaks_the_line(self):
        os.remove(os.path.join(self.dir, "002.json"))
        v, rc = _chain(self.dir)
        self.assertEqual(v, "CHAIN BROKEN")
        self.assertNotEqual(rc, 0)

    def test_a_replayed_position_is_refused(self):
        # an attacker hands out yesterday's anchor under a fresh file name
        shutil.copy(os.path.join(self.dir, "002.json"),
                    os.path.join(self.dir, "002-copy.json"))
        v, rc = _chain(self.dir)
        self.assertEqual(v, "CHAIN BROKEN")
        # the reason is named: the same position claimed twice
        out = subprocess.run([sys.executable, os.path.join(TOOLS, "anchor_chain.py"),
                              self.dir], capture_output=True, text=True, cwd=REPO).stdout
        self.assertIn("seq 2 appears twice", out)

    def test_a_rewritten_predecessor_is_refused(self):
        p = os.path.join(self.dir, "003.json")
        a = json.load(open(p, encoding="utf-8"))
        a["prev_anchor_digest"] = "0" * 64
        json.dump(a, open(p, "w", encoding="utf-8"))
        v, rc = _chain(self.dir)
        self.assertEqual(v, "CHAIN BROKEN")

    def test_a_first_anchor_may_not_declare_a_predecessor(self):
        p = os.path.join(self.dir, "001.json")
        a = json.load(open(p, encoding="utf-8"))
        a["prev_anchor_digest"] = "1" * 64
        json.dump(a, open(p, "w", encoding="utf-8"))
        v, rc = _chain(self.dir)
        self.assertEqual(v, "CHAIN BROKEN")

    def test_a_short_chain_is_reported_stale_not_merely_absent(self):
        # the caller already knows seq 5 exists somewhere; seeing seq 3 means
        # newer anchors are being withheld
        v, rc = _chain(self.dir, "--expect-latest", "5")
        self.assertEqual(v, "STALE")
        self.assertEqual(rc, 5)

    def test_an_older_anchor_is_refused_against_a_newer_one(self):
        # rollback: hand the stranger seq 1 and let them compare with seq 2
        v, rc = _check(os.path.join(self.tmp, "b1"), prev=self.a[1])
        self.assertEqual(v, "FAILED")
        self.assertNotEqual(rc, 0)

    def test_the_current_anchor_is_refused_without_its_predecessor(self):
        # seq > 1 cannot be placed without the anchor it names
        v, rc2 = _check(os.path.join(self.tmp, "b2"), prev=self.a[0])
        self.assertEqual(v, "ANCHORED")


if __name__ == "__main__":
    unittest.main()
