"""A lab bundle must carry its evidence, not assert it.

Four things are checkable and therefore refused when missing: the bytes recompute,
a hostile control scored below full marks, the exit code exists, and the runner
declared what they knew. The tests build a real bundle with the real tool, then
break one thing at a time.
"""
import json
import os
import tempfile
import subprocess
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO, "tools"))

LAB = os.path.join(_REPO, "tools", "lab_manifest.py")
CHK = os.path.join(_REPO, "tools", "check_lab_bundle.py")


def _tmpdir():
    """A fresh directory per call: a shared one lets earlier runs leak into later bundles."""
    return tempfile.mkdtemp(prefix="labtest_")


class TestABuiltBundleIsAcceptable(unittest.TestCase):
    def setUp(self):
        self.root = _tmpdir()
        for name, body in (("run.log", b"strict 36/36\n"), ("receipt.json", b'{"cases": 36}\n')):
            with open(os.path.join(self.root, name), "wb") as f:
                f.write(body)
        self.archive = os.path.join(self.root, "uibc-conformance-0.4.1.zip")
        with open(self.archive, "wb") as f:
            f.write(b"PK\x05\x06" + b"0" * 200)
        self.bundle = os.path.join(self.root, "lab_bundle.json")
        subprocess.run([sys.executable, LAB, "--dir", self.root, "--archive", self.archive,
                        "--question", "does it reject a flipped byte",
                        "--claim", "the corpus decides this",
                        "--runner", "A Stranger <s@example.org>",
                        "--blind", "blind",
                        "--command", "python run.py", "--exit-code", "0",
                        "--stdout-tail", "strict 36/36",
                        "--positive-what", "clean package", "--positive-result", "PASS",
                        "--hostile-what", "accept-all verifier", "--hostile-result", "6/36",
                        "--cases-total", "36",
                        "--negative-what", "no verifier", "--negative-result", "exit 3, no receipt",
                        "--limits", "one corpus; no anchor",
                        "--out", self.bundle],
                       check=True, capture_output=True)
        with open(self.bundle, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_it_digests_the_run_directory_and_the_archive(self):
        names = sorted(e["path"] for e in self.data["bytes"])
        self.assertEqual(names, ["receipt.json", "run.log"])
        self.assertEqual(self.data["kind"], "uibc-lab-bundle-v0")
        self.assertEqual(len(self.data["archive"]["sha256"]), 64)

    def test_the_checker_accepts_a_bundle_it_can_recompute(self):
        proc = subprocess.run([sys.executable, CHK, self.bundle, "--dir", self.root,
                               "--archive", self.archive], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("ACCEPTABLE", proc.stdout)

    def test_a_tampered_byte_is_refused(self):
        with open(os.path.join(self.root, "run.log"), "ab") as f:
            f.write(b"and one more line\n")
        proc = subprocess.run([sys.executable, CHK, self.bundle, "--dir", self.root],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("does not hash to its recorded digest", proc.stdout)


class TestItRefusesTheFourClaimsWhenUnsupported(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, os.path.join(_REPO, "tools"))
        import check_lab_bundle as c
        self.c = c
        self.good = {
            "kind": c.KIND,
            "question": "q",
            "claim": "c",
            "archive": {"path": "a.zip", "bytes": 1, "sha256": "a" * 64},
            "roles": {"runner": "A Stranger <s@example.org>"},
            "exposure": {"blind": "directed", "declared_by": "A Stranger",
                         "declared_utc": "2026-11-20T04:05:06Z"},
            "run": {"command": "python run.py", "exit_code": 0, "stdout_tail": "strict 36/36"},
            "controls": {"positive": {"result": "PASS"},
                         "hostile": {"result": "6/36", "cases_total": 36},
                         "negative": {"result": "exit 3, no receipt"}},
            "limits": ["one corpus"],
            "bytes": [{"path": "run.log", "bytes": 1, "sha256": "b" * 64}],
        }

    def test_the_good_bundle_passes(self):
        self.assertEqual(self.c.check(self.good), [])

    def test_a_hostile_control_at_full_marks_is_refused(self):
        self.good["controls"]["hostile"]["result"] = "36/36"
        reasons = self.c.check(self.good)
        self.assertTrue(any("full marks" in r for r in reasons), reasons)

    def test_no_exit_code_is_refused(self):
        self.good["run"]["exit_code"] = None
        reasons = self.c.check(self.good)
        self.assertTrue(any("exit code" in r for r in reasons), reasons)

    def test_blank_exposure_is_refused(self):
        self.good["exposure"]["blind"] = ""
        reasons = self.c.check(self.good)
        self.assertTrue(any("exposure.blind" in r for r in reasons), reasons)

    def test_empty_limits_are_refused(self):
        self.good["limits"] = []
        reasons = self.c.check(self.good)
        self.assertTrue(any("no stated boundary" in r for r in reasons), reasons)

    def test_an_archive_that_is_not_on_disk_is_refused(self):
        reasons = self.c.check(self.good, archive=os.path.join(_tmpdir(), "nope.zip"))
        self.assertTrue(any("does not exist" in r for r in reasons), reasons)


class TestTheReleaseScriptMeasuresInsteadOfAsserting(unittest.TestCase):
    """The shipped release bundle must come from measurements, not prose."""

    SCRIPT = os.path.join(_REPO, "tools", "release_lab_bundle.py")
    ARCHIVE = os.path.join(_REPO, "conformance", "uibc-conformance-0.4.1.zip")

    def test_it_states_what_it_measures(self):
        text = open(self.SCRIPT, encoding="utf-8").read()
        for marker in ("Scenario A", "Scenario B", "Scenario C"):
            self.assertIn(marker, text)
        self.assertIn("must score far below full", text.lower() + text)

    def test_the_accept_all_stub_really_accepts_everything(self):
        """If the hostile control were itself broken, its score would mean nothing."""
        import re
        src = open(self.SCRIPT, encoding="utf-8").read()
        block = re.search(r'ACCEPT_ALL = """(.*?)"""', src, re.S).group(1)
        captured = {}
        exec(compile(block, "<accept_all>", "exec"),
             {"json": __import__("json"),
              "print": lambda s: captured.update(result=json.loads(s)["result"])})
        self.assertEqual(captured.get("result"), "PASS")

    @unittest.skipUnless(os.environ.get("UIBC_SLOW"), "set UIBC_SLOW=1 to run the full release script")
    def test_end_to_end_release_bundle(self):
        if not os.path.isfile(self.ARCHIVE):
            self.skipTest("no archive in this tree (sdist build)")
        out = _tmpdir()
        proc = subprocess.run([sys.executable, self.SCRIPT, "--version", "0.4.1", "--out", out],
                              capture_output=True, text=True, timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        with open(os.path.join(out, "uibc-lab-bundle-0.4.1.json"), encoding="utf-8") as f:
            bundle = json.load(f)
        total = bundle["controls"]["hostile"]["cases_total"]
        hostile = int(bundle["controls"]["hostile"]["result"].split("/")[0])
        self.assertLess(hostile, total, "the hostile control must not pass the corpus")
        self.assertIn("exit 3", bundle["controls"]["negative"]["result"])


if __name__ == "__main__":
    unittest.main()
