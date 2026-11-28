"""The profile's cases, replayed in two languages.

`conformance/profile/cases.json` records a verdict and an issuer state for each
case. These tests hold three things:

* the recorded verdicts are not chosen by hand -- a fresh build must reproduce
  both the bytes and the verdicts (`build --check`), and every recorded verdict
  must still be what the code says;
* the tier never reports `OK`, and every refusal code it defines is exercised;
* the Node implementation reaches the same verdict on the same bytes, so the
  profile is runnable in a second language rather than only in the one it was
  written in.

If `node` is not on PATH the Node test skips with that reason: a missing runtime
is not evidence that the two languages disagree.
"""

import json
import os
import subprocess
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from uibc_core import profile  # noqa: E402
from tools import run_profile_vectors as runner  # noqa: E402

CASES = os.path.join(_REPO, "conformance", "profile", "cases.json")
NODE = os.path.join(_REPO, "tools", "verify-js", "profile.mjs")


class TestVectorsAreReproducible(unittest.TestCase):
    def test_recorded_cases_match_a_fresh_build(self):
        out = subprocess.run([sys.executable, os.path.join(_REPO, "tools", "build_profile_vectors.py"),
                              "--check"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_every_case_replays_to_its_recorded_verdict(self):
        ok, doc, rows = runner.run()
        self.assertTrue(ok, [r for r in rows if not r["ok"]])
        self.assertEqual(len(rows), len(doc["cases"]))

    def test_every_refusal_code_is_exercised(self):
        doc = json.load(open(CASES, encoding="utf-8"))
        codes = {c["expected"]["verdict"] for c in doc["cases"]}
        for code in (profile.PARTIAL_INCLUSION_UNCHECKED, profile.FAIL_VALUE_MISMATCH,
                     profile.UNSUPPORTED_SCHEME, profile.FAIL_MALFORMED,
                     profile.FAIL_PACKAGE, profile.FAIL_UNTRUSTED_ISSUER):
            self.assertIn(code, codes, "no case produces %s" % code)

    def test_the_tier_never_says_ok(self):
        doc = json.load(open(CASES, encoding="utf-8"))
        self.assertNotIn(profile.OK, {c["expected"]["verdict"] for c in doc["cases"]})

    def test_issuer_state_is_separate_from_the_verdict(self):
        doc = json.load(open(CASES, encoding="utf-8"))
        by_id = {c["id"]: c["expected"] for c in doc["cases"]}
        self.assertEqual(by_id["good-trusted"]["issuer"], "TRUSTED")
        self.assertEqual(by_id["other-key"]["issuer"], "UNTRUSTED")
        self.assertEqual(by_id["good"]["issuer"], "NOT_CHECKED")
        # the verdict is the same for good and good-trusted: trust is its own axis
        self.assertEqual(by_id["good"]["verdict"], by_id["good-trusted"]["verdict"])


class TestSecondLanguage(unittest.TestCase):
    def test_node_reaches_the_same_verdict_on_the_same_bytes(self):
        try:
            subprocess.run(["node", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            self.skipTest("node not on PATH: %s" % exc)
        out = subprocess.run(["node", NODE, "--vectors", CASES],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0,
                         out.stdout + out.stderr)
        self.assertIn("python and node agree", out.stdout)

    def test_node_single_package_mode_agrees_with_python(self):
        try:
            subprocess.run(["node", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            self.skipTest("node not on PATH: %s" % exc)
        receipt = os.path.join(_REPO, "conformance", "profile", "cases", "other-key.cose")
        pub = subprocess.run([sys.executable, "-c",
                              "import sys;sys.path.insert(0,'.');"
                              "from uibc_core import ed25519;"
                              "print(ed25519.publickey(b'\\x11'*32).hex())"],
                             cwd=_REPO, capture_output=True, text=True).stdout.strip()
        pkg = os.path.join(_REPO, "examples", "demo.uibc")
        out = subprocess.run(["node", NODE, pkg, "--receipt", receipt,
                              "--trusted-issuer", pub],
                             capture_output=True, text=True, encoding="utf-8")
        res = json.loads(out.stdout)
        self.assertEqual(res["verdict"], profile.FAIL_UNTRUSTED_ISSUER)
        self.assertEqual(res["issuer"], "UNTRUSTED")


if __name__ == "__main__":
    unittest.main()
