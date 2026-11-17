"""S4 containment: a symlink must not let a package hash something outside itself.

Found by running tools/redteam_suite.py on a Linux host on 2026-11-17 (case RT03):
the evidence file was replaced with a symlink pointing outside the package and the
verifier still returned PASS, because it hashed whatever the path resolved to. A
package that can make a verifier read an arbitrary file is not a package that
describes itself.

Symlinks need a privilege on Windows (Developer Mode or admin), so this test skips
there rather than reporting a failure it did not cause.
"""

import json
import os
import shutil
import tempfile
import unittest

from uibc_core.verify import verify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "fixtures", "clean.uibc")


def _supports_symlink(tmp):
    probe = os.path.join(tmp, "probe")
    target = os.path.join(tmp, "target")
    with open(target, "w", encoding="utf-8") as f:
        f.write("x")
    try:
        os.symlink(target, probe)
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False


class SymlinkContainmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s4link-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        if not _supports_symlink(self.tmp):
            raise unittest.SkipTest("this platform does not allow creating symlinks")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        shutil.copytree(BASE, self.pkg)

    def test_evidence_symlink_outside_the_package_fails_s4(self):
        index = json.load(open(os.path.join(self.pkg, "evidence", "index.json"),
                               encoding="utf-8"))
        entry = index["entries"][0]
        rel = entry["path"]
        inside = os.path.join(self.pkg, "evidence", rel)
        outside = os.path.join(self.tmp, "outside.txt")
        shutil.copyfile(inside, outside)          # same bytes, so only the link is suspect
        os.remove(inside)
        os.symlink(outside, inside)

        r = verify(self.pkg)
        checks = {c["id"]: c for c in r["checks"]}
        self.assertEqual(checks["S4"]["result"], "FAIL")
        self.assertIn("resolves outside the evidence root", checks["S4"]["detail"])
        self.assertEqual(r["result"], "FAIL")


if __name__ == "__main__":
    unittest.main()
