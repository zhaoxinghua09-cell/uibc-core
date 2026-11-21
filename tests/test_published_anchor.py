"""The anchor in anchors/001 has to keep verifying, or the repository is lying.

This is the check that would have caught every anchor this project ever
"published" as a diagram. It runs offline, in CI, on every push: if the bytes in
anchors/001 stop matching the head the anchor pins, or the signature stops
verifying against the key it names, CI goes red before a reader finds out.

A second implementation has to agree, otherwise the check is only as good as the
implementation that wrote it.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANCHOR_DIR = os.path.join(REPO, "anchors", "001")
NODE = shutil.which("node")


def run(args, cwd=REPO):
    return subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True,
                          text=True, timeout=180)


@unittest.skipUnless(os.path.isdir(ANCHOR_DIR), "no published anchor in this tree")
class TestPublishedAnchor(unittest.TestCase):
    def test_anchor_json_is_well_formed(self):
        with open(os.path.join(ANCHOR_DIR, "anchor.json"), encoding="utf-8") as fh:
            a = json.load(fh)
        self.assertEqual(a["schema"], "uibc-anchor/0.1")
        self.assertEqual(a["seq"], 1)
        self.assertEqual(len(a["key_id"]), 64)
        self.assertTrue(a["checkpoint_head"].startswith("sha256:"))
        self.assertIsNone(a["prev_anchor_digest"], "seq 1 has no predecessor")
        # the demo seed is public; a published anchor must not be signed with it
        with open(os.path.join(REPO, "docs", "PUBLISHER-IDENTITY.md"), encoding="utf-8") as fh:
            self.assertNotIn(a["key_id"], fh, "this is the published demo key, not a real one")

    def test_python_verdict_is_anchored(self):
        r = run(["tools/anchor_check.py", ANCHOR_DIR])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ANCHORED", r.stdout)

    def test_the_chain_accepts_it(self):
        r = run(["tools/anchor_chain.py", ANCHOR_DIR, "--expect-latest", "1"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CHAIN OK", r.stdout)

    @unittest.skipUnless(NODE, "node is not installed here")
    def test_the_second_implementation_agrees(self):
        r = subprocess.run([NODE, "tools/verify-js/chain.mjs", ANCHOR_DIR,
                            "--expect-latest", "1"], cwd=REPO, capture_output=True,
                           text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CHAIN OK", r.stdout)

    def test_tampering_with_the_package_breaks_it(self):
        tmp = os.path.join(REPO, "anchors", "001_tamper_probe")
        shutil.copytree(ANCHOR_DIR, tmp)
        try:
            # the manifest is re-parsed, so trailing whitespace in it is not a
            # content change; the evidence file bytes are what the head covers
            victim = os.path.join(tmp, "package", "evidence", "files", "run-summary.txt")
            with open(victim, "a", encoding="utf-8") as fh:
                fh.write("one more line\n")
            r = run(["tools/anchor_check.py", tmp])
            self.assertNotEqual(r.returncode, 0, "a modified package still verified")
            self.assertIn("FAIL", r.stdout.upper() + r.stderr.upper())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
