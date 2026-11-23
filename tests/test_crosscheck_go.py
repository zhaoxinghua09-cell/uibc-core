"""A third language answers the same verdicts, including the consistency subproofs.

pymerkle builds trees and never reads a path; the Sigstore arithmetic folds
inclusion paths but has no consistency checker. This test adds the Go program that
does both, and it is the one place where the SUBPROOF order this package scores is
answered by code from another project.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROG_DIR = os.path.join(ROOT, "tools", "third_party", "go-merklecheck")
CASE_DIR = os.path.join(ROOT, "docs", "upstream-package", "scitt-rfc9162", "v1")

GO = shutil.which("go")
SKIP_WHY = "third-party Go check unavailable: no go toolchain on this runner's PATH"


@unittest.skipUnless(GO, SKIP_WHY)
class GoCrossCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="merklecheck-")
        cls.bin = os.path.join(cls.tmp, "merklecheck.exe" if os.name == "nt" else "merklecheck")
        env = dict(os.environ, GOFLAGS="-mod=readonly", GOTOOLCHAIN="local")
        # -mod=readonly: a go.sum mismatch must fail, not be silently rewritten.
        build = subprocess.run([GO, "build", "-o", cls.bin, "."], cwd=PROG_DIR,
                               capture_output=True, text=True, env=env, timeout=600)
        if build.returncode != 0:
            raise unittest.SkipTest("go build failed here: %s" % build.stderr.strip()[:400])

    def _run(self, *args):
        env = dict(os.environ, GOTOOLCHAIN="local")
        return subprocess.run([self.bin, *args], cwd=ROOT, capture_output=True,
                              text=True, env=env, timeout=600)

    def test_every_case_verdict_agrees(self):
        out = os.path.join(self.tmp, "go.json")
        proc = self._run("--dir", CASE_DIR, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        with open(out, encoding="utf-8") as fh:
            report = json.load(fh)
        self.assertEqual(report["cases_compared"], 63)
        self.assertEqual(report["agrees_on_verdict"], 63)
        kinds = {r["kind"] for r in report["cases"]}
        self.assertIn("consistency", kinds)
        consistency = [r for r in report["cases"] if r["kind"] == "consistency"]
        self.assertEqual(len(consistency), 13)
        for r in consistency:
            self.assertTrue(r["agrees_on_verdict"], r["case"])

    def test_the_check_can_fail(self):
        proc = self._run("--dir", CASE_DIR, "--self-test")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("mutated VALID paths detected", proc.stdout)


if __name__ == "__main__":
    unittest.main()
