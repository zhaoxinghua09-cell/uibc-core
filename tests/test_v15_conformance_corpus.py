"""The published conformance corpus must reproduce, and must stay reproducible.

Two independent assertions, because they fail for different reasons:
  1. `tools/conformance_vectors.py --check` - the file on disk equals a fresh build,
     so a vector cannot be edited by hand to match a broken implementation;
  2. `tools/conformance_check.py` - a checker that imports nothing from `uibc_core`
     reproduces every expected value. If our canonicalizer drifts, this fails.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConformanceCorpusTests(unittest.TestCase):
    def test_corpus_reproduces_from_generator(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "conformance_vectors.py"),
                            "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_corpus_checks_with_a_foreign_implementation(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "conformance_check.py")],
                           capture_output=True, text=True)
        if r.returncode == 2 and "cryptography" in (r.stdout + r.stderr):
            self.skipTest("cryptography not installed")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("29/29", r.stdout)


if __name__ == "__main__":
    unittest.main()
