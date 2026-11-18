"""The JavaScript verifier must keep agreeing with the Python one where it claims
to agree, and must keep saying "I cannot decide" where it cannot.

These tests skip when Node is absent: the suite has to stay green on a machine
without it, but the moment Node is there, the two implementations are held to
each other.
"""
import hashlib
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
COVERED = ("S1", "S2", "S4", "S5", "S6", "S7", "S8", "S9", "S10", "S11", "S12", "S13",
           "S14", "S15", "S16", "S17", "S18")


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

    def test_a_real_rfc3161_token_is_verified_and_every_mutation_is_refused(self):
        """The one witness we cannot mint.

        The token in `tests/fixtures/anchor/` was issued by Free TSA on
        2026-11-17 for the head recorded beside it. This test does not trust
        that claim: it re-verifies the CMS signature with Node's own crypto,
        from the token's own bytes, and then tries to break it five ways.

        The last assertion is the one that matters most: the second
        implementation and the Python one must reach the same verdict on a
        third party's artefact, because neither of them made it.
        """
        from uibc_core import tsa

        anchor = os.path.join(_REPO, "tests", "fixtures", "anchor")
        tsr = os.path.join(anchor, "freetsa.tsr")
        ca = os.path.join(anchor, "freetsa_ca.pem")
        head = os.path.join(anchor, "anchored_head.json")
        digest = hashlib.sha256(open(head, "rb").read()).hexdigest()

        def js_token(token_path, expected, ca_path):
            out = subprocess.run(["node", os.path.join(_REPO, "tools", "verify-js", "rfc3161.mjs"),
                                  token_path, expected, ca_path],
                                 capture_output=True, text=True)
            return json.loads(out.stdout)

        good = js_token(tsr, digest, ca)
        self.assertTrue(good["ok"], good["problems"])
        self.assertEqual(good["info"]["gen_time"], "20261117081135Z")
        self.assertIn("Free TSA", good["info"]["ca"])

        # 1. the bytes are what they are: a flipped bit must break the signature
        tampered = tempfile.mkdtemp(prefix="uibc-tsr-")
        body = open(tsr, "rb").read()
        flipped = bytearray(body)
        flipped[-100] ^= 0x01
        bad_path = os.path.join(tampered, "flipped.tsr")
        open(bad_path, "wb").write(bytes(flipped))
        self.assertFalse(js_token(bad_path, digest, ca)["ok"])

        # 2. anchoring the wrong data must be refused, not tolerated
        self.assertFalse(js_token(tsr, "0" * 64, ca)["ok"])

        # 3. a CA that did not issue this certificate proves nothing
        self.assertFalse(js_token(tsr, digest, os.path.join(anchor, "freetsa_ca.pem") + ".missing")["ok"])

        # 4. no CA at all is an unsigned claim about who signed
        self.assertFalse(js_token(tsr, digest, "")["ok"])

        # 5. the Python verifier must agree with the JavaScript one
        body_bytes = open(tsr, "rb").read()
        bundle = open(ca, "rb").read()
        py_ok, _info, py_problems = tsa.verify_token(body_bytes, bytes.fromhex(digest), bundle)
        self.assertTrue(py_ok, py_problems)

    def test_the_out_of_band_pin_is_checked_the_same_way_in_both_languages(self):
        """S9 is the one check no package can perform on itself.

        An older package that is perfectly self-consistent is indistinguishable
        from the current one unless somebody recorded the head elsewhere. The
        pinned value therefore arrives as an argument, never as a package field:
        if it came from the package it would be the thing being checked.

        Both implementations must reach the same verdict for the same pin, and
        both must fail for a pin that is merely plausible-looking.
        """
        from uibc_core.verify import verify

        pkg = os.path.join(cases_root(), "04-a-package-with-a-checkpoint-appended")
        head = json.load(open(os.path.join(pkg, "manifest.json"), encoding="utf-8"))["checkpoint_head"]

        def pinned(expect):
            out = subprocess.run(["node", _JS, pkg, "--expect-head", expect],
                                 capture_output=True, text=True)
            report = json.loads(out.stdout)
            return {c["id"]: c["result"] for c in report["checks"]}["S9"]

        def pinned_py(expect):
            report = verify(pkg, expect_head=expect)
            return {c["id"]: c["result"] for c in report["checks"]}["S9"]

        self.assertEqual(pinned(head), "PASS")
        self.assertEqual(pinned_py(head), "PASS")
        wrong = "sha256:" + "0" * 64
        self.assertEqual(pinned(wrong), "FAIL")
        self.assertEqual(pinned_py(wrong), "FAIL")
        # With no pin supplied the check is not reported at all: an unchecked
        # rollback must not masquerade as a passed check.
        report = js(pkg)
        self.assertNotIn("S9", [c["id"] for c in report["checks"]])

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
