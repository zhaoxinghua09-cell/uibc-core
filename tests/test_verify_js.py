"""The JavaScript verifier must keep agreeing with the Python one where it claims
to agree, and must keep saying "I cannot decide" where it cannot.

These tests skip when Node is absent: the suite has to stay green on a machine
without it, but the moment Node is there, the two implementations are held to
each other.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_JS = os.path.join(_REPO, "tools", "verify-js", "verify.mjs")
_ZIP = os.path.join(_REPO, "conformance", "uibc-conformance-0.4.0.zip")

NODE = shutil.which("node")


def cases_root():
    """The repo ships only the archive; unpack it once when cases/ is absent."""
    direct = os.path.join(_REPO, "conformance", "cases")
    if os.path.isdir(direct):
        return direct
    tmp = tempfile.mkdtemp(prefix="uibc-js-cases-")
    with zipfile.ZipFile(_ZIP) as z:
        z.extractall(tmp)
    return os.path.join(tmp, "cases")
COVERED = ("S1", "S2", "S4", "S5", "S6", "S7", "S10", "S11", "S12", "S13", "S14")


def js(pkg):
    out = subprocess.run(["node", _JS, pkg], capture_output=True, text=True)
    return json.loads(out.stdout)


def failed(report):
    return {c["id"] for c in report["checks"] if str(c["result"]).upper() == "FAIL"}


@unittest.skipUnless(NODE, "node is not installed")
class TestJavaScriptVerifier(unittest.TestCase):
    def test_a_sound_package_is_inconclusive_rather_than_pass(self):
        report = js(os.path.join(cases_root(), "01-the-shipped-package-untouched"))
        self.assertEqual(report["result"], "INCONCLUSIVE")
        self.assertEqual(failed(report), set())
        self.assertIn("not checked here", report["note"])
        self.assertEqual(sorted(report["covered"] if "covered" in report else
                                [c["id"] for c in report["checks"]]),
                         ["S1", "S11", "S12", "S2", "S4", "S5", "S6", "S7"])

    def test_it_catches_a_changed_byte_and_the_root(self):
        case = os.path.join(cases_root(), "06-flip-one-byte-in-evidence")
        self.assertIn("S4", failed(js(case)))
        case = os.path.join(cases_root(), "09-edit-the-evidence-root")
        self.assertIn("S5", failed(js(case)))

    def test_it_names_the_check_python_names(self):
        """The suite's own criterion: the expected check must be among the failures.

        The two verifiers need not report identical sets. Python stops after S4
        and does not recompute the root; this one does both, so on a changed
        byte it reports S5 as well. Any extra check has to be a downstream
        consequence, never an invented one.
        """
        manifest = json.load(open(os.path.join(_REPO, "conformance", "manifest.json"),
                                  encoding="utf-8"))
        checked = 0
        for case in manifest["cases"]:
            expected = set(case.get("expected_checks") or [])
            if not expected or not expected & set(COVERED):
                continue
            rel = case["path"].split("/", 1)[1] if case["path"].startswith("cases/") else case["path"]
            js_fail = failed(js(os.path.join(cases_root(), rel)))
            self.assertTrue(expected & js_fail, case["attack"])
            # Extra findings are fine -- a deregistered entry is both an
            # undeclared file (S1) and a count mismatch (S12) as well as a root
            # mismatch. What must never happen is a verdict from a check the
            # implementation does not claim to run.
            self.assertLessEqual(js_fail - expected, set(COVERED), case["attack"])
            checked += 1
        self.assertGreaterEqual(checked, 8)

    def test_the_positive_cases_are_not_refused(self):
        for name in os.listdir(cases_root()):
            if not name[:2] in ("01", "02", "03", "04", "05"):
                continue
            report = js(os.path.join(cases_root(), name))
            self.assertEqual(report["result"], "INCONCLUSIVE", name)
            self.assertEqual(failed(report), set(), name)


if __name__ == "__main__":
    unittest.main()
