"""The conformance archive must be runnable without installing anything.

Before 2026-11-20 it was not: the archive called an installed package, so a
machine without `pip install uibc-core` produced 36 rows of FAIL and a receipt.
That receipt is indistinguishable from "these packages all fail".

The archive now carries `uibc_core.pyz`, and run.py prefers it. These tests keep
that true: the file is present, it is a real zip with the package inside, and it
actually verifies a shipped package when executed.
"""
import hashlib
import json
import os
import subprocess
import sys
import unittest
import zipfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARCHIVE = os.path.join(_REPO, "conformance", "uibc-conformance-0.4.1.zip")


class TestArchiveCarriesItsVerifier(unittest.TestCase):
    def test_the_single_file_verifier_ships_in_the_archive(self):
        self.assertTrue(os.path.isfile(ARCHIVE), "archive missing")
        with zipfile.ZipFile(ARCHIVE) as z:
            names = z.namelist()
            self.assertIn("uibc_core.pyz", names,
                          "archive no longer carries a verifier; a machine without "
                          "pip would report 0/36")
            self.assertIn("run.py", names)
            data = z.read("uibc_core.pyz")
        self.assertGreater(len(data), 50000, "pyz is too small to contain the package")
        # it must be a zip, since that is what python executes for a .pyz
        self.assertEqual(data[:2], b"PK")

    def test_run_py_prefers_the_bundled_verifier(self):
        """A stranger with no installed package should still get 36/36."""
        sys.path.insert(0, os.path.join(_REPO, "tools"))
        import conformance_bundle_run as runner
        text = runner.__file__
        with open(text, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("uibc_core.pyz", src,
                      "run.py no longer looks for the bundled verifier")

    def test_the_bundled_verifier_verifies_and_reports_a_version(self):
        tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "pyzcheck")
        os.makedirs(tmp, exist_ok=True)
        pyz = os.path.join(tmp, "uibc_core.pyz")
        with zipfile.ZipFile(ARCHIVE) as z:
            with open(pyz, "wb") as f:
                f.write(z.read("uibc_core.pyz"))
        case = os.path.join(_REPO, "fixtures", "clean.uibc")
        proc = subprocess.run([sys.executable, pyz, "verify", case],
                              capture_output=True, text=True, timeout=120)
        out = json.loads(proc.stdout)
        # Exactly INCONCLUSIVE, not "PASS or INCONCLUSIVE". The old assertion
        # accepted either, which is the shape of a test that cannot fail: it
        # tolerated the documented `clean -> PASS` and the real behaviour
        # disagreeing for as long as they liked. `fixtures/clean.uibc` is a
        # v0.3.0 HMAC-sealed package; a 0.4.1 verifier has nothing to check the
        # seal against, and reading it as PASS would be the wrong answer.
        self.assertEqual(out["result"], "INCONCLUSIVE", proc.stderr[-300:])
        ver = subprocess.run([sys.executable, pyz, "--version"],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(ver.returncode, 0)
        self.assertTrue(ver.stdout.strip(), "--version printed nothing")


if __name__ == "__main__":
    unittest.main()
