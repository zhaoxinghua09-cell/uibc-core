"""Quickstart check: what a fresh clone can and cannot run, and in what order.

Written because an anonymous clone of the public branch failed 18 tests with
FireNotFound-style path errors: the tests need the materialised corpus, the corpus
needs the mutation run, and nothing said so. This test asserts the ordering works
and that the corpus builder now seeds itself.

It is deliberately cheap: it does not run the mutation benchmark unless the
corpus is genuinely missing (then it does, which is the point).
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "benchmark", "corpus")
BASE = os.path.join(CORPUS, "base")


class TestQuickstart(unittest.TestCase):
    def test_corpus_builder_is_self_seeding(self):
        if os.path.isdir(BASE):
            self.skipTest("corpus already present; self-seeding path not exercised")
        rc = subprocess.call([sys.executable,
                              os.path.join(ROOT, "benchmark", "corpus.py")],
                             cwd=ROOT)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isdir(BASE),
                        "corpus.py returned success without producing base/")

    def test_public_entrypoints_exist(self):
        for rel in ("uibc_core/verify.py", "uibc_core/composition.py",
                    "independent_verifier/iverify.py", "benchmark/run.py",
                    "tools/eqms_contract.py", "tools/pccp_case.py"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)), rel)


if __name__ == "__main__":
    unittest.main()
