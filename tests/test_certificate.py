"""Certificate v0.1 tests (task G3). Stdlib unittest only."""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import cli as ucli
from uibc_core.certificate import CERT_SCHEMA, issue_certificate, verify_certificate
from uibc_core.signing import generate_key, key_id


def _make_pkg(tmp, key, name="c.uibc"):
    pkg = os.path.join(tmp, name)
    ucli.cmd_init(type("A", (), {"path": pkg})())
    ucli.cmd_register(type("A", (), {
        "path": pkg, "agent_id": "cert-agent", "owner": "cert-owner",
        "agent_type": "software-agent", "version": "1"})())
    src = os.path.join(tmp, "ev.txt")
    with open(src, "w", encoding="utf-8") as f:
        f.write(f"cert evidence for {name}\n")
    for i in range(2):
        ucli.cmd_evidence(type("A", (), {
            "path": pkg, "type": "OUTPUT", "file": src,
            "media_type": "text/plain", "note": f"n{i}"})())
    ucli.cmd_submit(type("A", (), {"path": pkg, "key": None})())
    return pkg


class CertificateTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.key = generate_key()
        self.other = generate_key()
        self.pkg = _make_pkg(self.tmp, self.key)
        with open(os.path.join(self.pkg, "identity.json"), encoding="utf-8") as f:
            self.identity = json.load(f)
        with open(os.path.join(self.pkg, "manifest.json"), encoding="utf-8") as f:
            self.manifest = json.load(f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _issue(self, **kw):
        return issue_certificate(self.key, self.identity, self.manifest, **kw)

    # 1. issue -> verify PASS
    def test_01_issue_verify_pass(self):
        cert = self._issue()
        r = verify_certificate(self.key, cert, package_dir=self.pkg)
        self.assertEqual(r["result"], "PASS")
        self.assertEqual(r["subject_agent"], "cert-agent")

    # 2. tampered body -> FAIL C5
    def test_02_tampered_cert_fails(self):
        cert = self._issue()
        cert["subject_agent"] = "someone-else"
        r = verify_certificate(self.key, cert)
        self.assertEqual(r["result"], "FAIL")
        ids = {c["id"]: c["result"] for c in r["checks"]}
        self.assertEqual(ids["C5"], "FAIL")

    # 3. wrong key -> FAIL C4
    def test_03_wrong_key_fails(self):
        cert = self._issue()
        r = verify_certificate(self.other, cert)
        self.assertEqual(r["result"], "FAIL")

    # 4. expired -> FAIL C6 (deterministic time travel)
    def test_04_expired_fails(self):
        cert = self._issue(expires_at="2026-01-01T00:00:00Z")
        r = verify_certificate(self.key, cert)
        self.assertEqual(r["result"], "FAIL")

    # 5. not yet expired -> PASS with future override time
    def test_05_not_expired_passes(self):
        cert = self._issue(expires_at="2099-01-01T00:00:00Z")
        r = verify_certificate(self.key, cert, now_utc="2026-09-18T00:00:00Z")
        self.assertEqual(r["result"], "PASS")

    # 6. bound to a DIFFERENT package -> FAIL C7
    def test_06_wrong_package_binding_fails(self):
        cert = self._issue()
        other_pkg = _make_pkg(self.tmp, generate_key(), name="c2.uibc")
        r = verify_certificate(self.key, cert, package_dir=other_pkg)
        self.assertEqual(r["result"], "FAIL")

    # 7. malformed cert (missing fields) -> FAIL C1
    def test_07_malformed_fails(self):
        r = verify_certificate(self.key, {"schema": CERT_SCHEMA})
        self.assertEqual(r["result"], "FAIL")

    # 8. CLI roundtrip: cert-issue -> cert-verify exit 0; tampered -> exit 1
    def test_08_cli_roundtrip(self):
        import subprocess
        kf = os.path.join(self.tmp, "owner.key")
        with open(kf, "w", encoding="ascii") as f:
            f.write(self.key.hex())
        py = sys.executable
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ, PYTHONPATH=root, PYTHONIOENCODING="utf-8")
        certf = os.path.join(self.tmp, "c.cert.json")
        r1 = subprocess.run(
            [py, "-m", "uibc_core.cli", "cert-issue", self.pkg,
             "--key", kf, "--out", certf, "--expires-days", "365"],
            capture_output=True, text=True, env=env)
        self.assertEqual(r1.returncode, 0)
        r2 = subprocess.run(
            [py, "-m", "uibc_core.cli", "cert-verify", certf,
             "--key", kf, "--package", self.pkg],
            capture_output=True, text=True, env=env)
        self.assertEqual(r2.returncode, 0)
        # tamper then expect failure
        with open(certf, encoding="utf-8") as f:
            cert = json.load(f)
        cert["owner"] = "mallory"
        with open(certf, "w", encoding="utf-8") as f:
            json.dump(cert, f)
        r3 = subprocess.run(
            [py, "-m", "uibc_core.cli", "cert-verify", certf, "--key", kf],
            capture_output=True, text=True, env=env)
        self.assertEqual(r3.returncode, 1)

    # 9. cert is NOT trust: report scope must state limits (report discipline)
    def test_09_report_states_scope(self):
        r = verify_certificate(self.key, self._issue())
        self.assertIn("NOT checked", r["scope"])
        self.assertIn("revocation", r["scope"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
