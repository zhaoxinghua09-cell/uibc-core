"""A verifier must not call a foreign container broken.

Measured 2026-11-20, before this guard existed: `independent_verify` was run
against the 13 published EATF vectors (Apache-2.0 repository, cloned and run
locally). It returned FAIL on all five packages that are valid under that
project's own contract, and "agreed" on the other eight only because FAIL was
the wrong answer for a reason it could not see. A FAIL there is an affirmative
claim about a format this implementation never read.
"""

import os
import sys
import tempfile
import unittest
import zipfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from independent_verifier.iverify import independent_verify


def _foreign_dir(root):
    """Something that is unmistakably not a UIBC package: a zip, plus a stray file."""
    path = os.path.join(root, "foreign")
    os.makedirs(path)
    with zipfile.ZipFile(os.path.join(path, "package.aep"), "w") as z:
        z.writestr("canonical.bin", "xx")
        z.writestr("metadata.json", "{}")
    with open(os.path.join(path, "README.md"), "w", encoding="utf-8") as f:
        f.write("not a uibc package\n")
    return path


class TestForeignContainer(unittest.TestCase):
    def test_a_non_uibc_directory_is_declined_not_judged(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _foreign_dir(tmp)
            r = independent_verify(d)
        self.assertEqual(r["result"], "INCONCLUSIVE")
        self.assertEqual(r.get("unsupported"), "not-a-uibc-package")
        self.assertEqual(r["checked"], [])
        self.assertTrue(r["unjudged"])
        self.assertIn("not a UIBC package", r["statement"])

    def test_a_missing_path_is_declined_not_judged(self):
        r = independent_verify(os.path.join(_REPO, "no-such-package"))
        self.assertEqual(r["result"], "INCONCLUSIVE")
        self.assertEqual(r.get("unsupported"), "not-a-uibc-package")

    def test_a_real_package_is_still_judged(self):
        r = independent_verify(os.path.join(_REPO, "conformance", "oracle",
                                            "cases", "oracle-clean"))
        self.assertIsNone(r.get("unsupported"))
        self.assertIn(r["result"], ("PASS", "FAIL", "INCONCLUSIVE"))
        self.assertIn("V1", r["checks"])

    def test_a_broken_uibc_package_is_still_failed(self):
        """The guard must not swallow a package that has UIBC files but is wrong."""
        r = independent_verify(os.path.join(_REPO, "conformance", "oracle",
                                            "cases", "oracle-tampered"))
        self.assertIsNone(r.get("unsupported"))
        self.assertEqual(r["result"], "FAIL")


if __name__ == "__main__":
    unittest.main()
