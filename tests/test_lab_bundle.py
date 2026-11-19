"""A lab bundle must carry its evidence, not assert it.

Four things are checkable and therefore refused when missing: the bytes recompute,
a hostile control scored below full marks, the exit code exists, and the runner
declared what they knew. The tests build a real bundle with the real tool, then
break one thing at a time.
"""
import json
import os
import subprocess
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO, "tools"))

LAB = os.path.join(_REPO, "tools", "lab_manifest.py")
CHK = os.path.join(_REPO, "tools", "check_lab_bundle.py")


def _tmpdir():
    path = os.path.join(os.environ.get("TEMP", "/tmp"), "labtest")
    os.makedirs(path, exist_ok=True)
    return path


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


if __name__ == "__main__":
    unittest.main()
