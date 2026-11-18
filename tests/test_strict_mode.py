"""The one gap the docs kept admitting, closed behind a flag.

Before this, a file dropped into evidence/ that the index never promised stayed
a note. The reason was real: the format itself puts the tree, the chain, the
anchors and the policy artefacts there, so failing every undeclared file broke
every existing package. The fix is a mode, not a blanket change: --strict fails
uncommitted files and exempts the structural ones.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import outsider_audit as oa
from uibc_core.verify import verify

CLEAN = os.path.join(_REPO, "fixtures", "clean.uibc")


def s1(report):
    return next(c for c in report["checks"] if c["id"] == "S1")


class TestStrictMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _extra(self):
        pkg = oa._prepare(CLEAN, self.tmp)
        with open(os.path.join(pkg, "evidence", "extra.txt"), "w") as f:
            f.write("an uncommitted note\n")
        return pkg

    def test_lenient_mode_only_notes(self):
        pkg = self._extra()
        r = verify(pkg)
        self.assertEqual(s1(r)["result"], "PASS")
        self.assertIn("extra.txt", s1(r)["detail"])
        self.assertFalse(r["strict"])

    def test_strict_mode_fails_the_uncommitted_file(self):
        pkg = self._extra()
        r = verify(pkg, strict=True)
        self.assertEqual(s1(r)["result"], "FAIL")
        self.assertIn("uncommitted files under evidence/", s1(r)["detail"])
        self.assertEqual(r["result"], "FAIL")
        self.assertTrue(r["strict"])

    def test_structural_members_stay_exempt(self):
        pkg = oa._prepare(CLEAN, self.tmp)
        oa.build_v11(pkg)          # adds evidence/merkle.json and chain.json
        r = verify(pkg, strict=True)
        self.assertEqual(s1(r)["result"], "PASS",
                         "the format's own structural files must not be called uncommitted")

    def test_a_clean_package_passes_in_both_modes(self):
        for strict in (False, True):
            r = verify(CLEAN, strict=strict)
            self.assertEqual(s1(r)["result"], "PASS")

    def test_cli_exposes_the_flag(self):
        pkg = self._extra()
        out = subprocess.run([sys.executable, "-m", "uibc_core.cli", "verify", pkg,
                              "--strict"], capture_output=True, text=True, cwd=_REPO)
        self.assertIn('"strict": true', out.stdout)
        self.assertEqual(out.returncode, 1)


if __name__ == "__main__":
    unittest.main()
