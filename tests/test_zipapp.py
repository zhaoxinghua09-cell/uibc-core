"""One file, no install: the claim has to be run, not described.

Every outsider run so far needed the repository. A zipapp does not, so these
tests build one, run it from a directory that has no uibc_core on the path, and
require that it reaches the same verdicts and reports the same SPEC_ID as the
checkout it was built from - a verifier whose stated provenance changed with the
packaging would be reporting the packaging, not the code.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO, "tools"))

from build_zipapp import build  # noqa: E402
from make_release_bundle import DEMO_SEED, build as build_bundle  # noqa: E402


class TestZipapp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.pyz = os.path.join(cls.tmp, "uibc.pyz")
        build(cls.pyz)
        # a directory with nothing in it: no checkout, no uibc_core, no PYTHONPATH
        cls.isolated = os.path.join(cls.tmp, "isolated")
        os.makedirs(cls.isolated)
        cls.bundle = os.path.join(cls.tmp, "bundle")
        build_bundle(cls.bundle, DEMO_SEED)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _run(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        return subprocess.run([sys.executable, self.pyz] + list(args),
                              cwd=self.isolated, capture_output=True, text=True,
                              timeout=120, env=env)

    def test_verify_runs_without_the_checkout(self):
        r = self._run("verify", os.path.join(_REPO, "fixtures", "clean.uibc"))
        # exit 0 is reserved for PASS; an unresolved check is exit 1 with the
        # verdict spelled out, never a silent success
        self.assertEqual(r.returncode, 1, r.stderr[-400:])
        self.assertIn("INCONCLUSIVE", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_spec_id_matches_the_checkout(self):
        from uibc_core import spec_id
        r = self._run("verify", os.path.join(_REPO, "fixtures", "clean.uibc"))
        report = json.loads(r.stdout)
        self.assertEqual(report["spec_id"], spec_id())

    def test_anchor_command_is_the_same_check(self):
        r = self._run("anchor", self.bundle)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        self.assertIn("VERDICT: ANCHORED", r.stdout)

    def test_anchor_refuses_a_forged_bundle(self):
        forged = os.path.join(self.tmp, "forged")
        shutil.copytree(self.bundle, forged)
        victim = os.path.join(forged, "package", "evidence", "files", "action-log.txt")
        open(victim, "wb").write(b"tampered\n")
        r = self._run("anchor", forged)
        self.assertEqual(r.returncode, 1, r.stdout[-400:])
        self.assertIn("VERDICT: FAILED", r.stdout)


if __name__ == "__main__":
    unittest.main()
