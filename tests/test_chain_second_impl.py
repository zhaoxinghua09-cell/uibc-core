"""The line of anchors, judged by both implementations.

Python (`tools/anchor_chain.py`) and Node (`tools/verify-js/chain.mjs`) share no
code. A verdict only one of them can produce is a verdict nobody can check, so
every scenario here is asserted twice and compared.
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
SEEDS = ["11" * 32, "22" * 32, "33" * 32]


def _node():
    for name in ("node", "nodejs"):
        p = shutil.which(name)
        if p:
            return p
    return None


NODE = _node()


def _build(out, seed, prev=None):
    cmd = [sys.executable, os.path.join(TOOLS, "make_release_bundle.py"),
           "--out", out, "--seed-hex", seed]
    if prev:
        cmd += ["--prev-anchor", prev]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    if r.returncode != 0:
        raise AssertionError("build failed: " + r.stderr[-300:])
    return os.path.join(out, "anchor.json")


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    lines = [l for l in r.stdout.splitlines() if l.startswith("VERDICT")]
    return (lines[0].split(":", 1)[1].strip() if lines else None), r.returncode


@unittest.skipIf(NODE is None, "node is not installed")
class TestChainSecondImplementation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="chain2-")
        self.dir = os.path.join(self.tmp, "anchors")
        os.makedirs(self.dir)
        prev = None
        for i, seed in enumerate(SEEDS, start=1):
            path = _build(os.path.join(self.tmp, "b%d" % i), seed, prev)
            prev = path
            shutil.copy(path, os.path.join(self.dir, "%03d.json" % i))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def both(self, *extra):
        py, prc = _run([sys.executable, os.path.join(TOOLS, "anchor_chain.py"),
                        self.dir, *extra])
        js, jrc = _run([NODE, os.path.join(TOOLS, "verify-js", "chain.mjs"),
                        self.dir, *extra])
        return (py, prc), (js, jrc)

    def assertAgree(self, *extra):
        (py, prc), (js, jrc) = self.both(*extra)
        self.assertEqual(py, js, "implementations disagree: python=%r node=%r" % (py, js))
        self.assertEqual(prc == 0, jrc == 0)
        return py, prc

    def test_a_sound_line_agrees(self):
        v, rc = self.assertAgree()
        self.assertEqual(v, "CHAIN OK")
        self.assertEqual(rc, 0)

    def test_a_gap_agrees(self):
        os.remove(os.path.join(self.dir, "002.json"))
        v, _ = self.assertAgree()
        self.assertEqual(v, "CHAIN BROKEN")

    def test_a_replay_agrees(self):
        shutil.copy(os.path.join(self.dir, "002.json"),
                    os.path.join(self.dir, "999.json"))
        v, _ = self.assertAgree()
        self.assertEqual(v, "CHAIN BROKEN")

    def test_a_rewritten_predecessor_agrees(self):
        p = os.path.join(self.dir, "003.json")
        a = json.load(open(p, encoding="utf-8"))
        a["prev_anchor_digest"] = "0" * 64
        json.dump(a, open(p, "w", encoding="utf-8"))
        v, _ = self.assertAgree()
        self.assertEqual(v, "CHAIN BROKEN")

    def test_a_withheld_newer_anchor_agrees_on_stale(self):
        v, rc = self.assertAgree("--expect-latest", "5")
        self.assertEqual(v, "STALE")
        self.assertEqual(rc, 5)

    def test_the_whole_thing_runs_from_an_empty_directory(self):
        # the end-to-end rehearsal: build, link, judge with both implementations
        # in a stripped environment. One command, under a second.
        r = subprocess.run([sys.executable, os.path.join(TOOLS, "outsider_chain_audit.py")],
                           capture_output=True, text=True, cwd=REPO)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERDICT: OK", r.stdout)
        for row in ("the line is sound", "newest bundle matches its anchor",
                    "superseded bundle is refused", "a withheld anchor is called stale"):
            self.assertIn(row, r.stdout)


if __name__ == "__main__":
    unittest.main()
