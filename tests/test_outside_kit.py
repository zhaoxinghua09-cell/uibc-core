"""The archive an outsider receives: does it run, and can it be checked?

A kit nobody can verify is a tarball with a promise attached. These tests
build one, run it in a directory that has nothing else, and then alter it to
confirm the checksum list actually notices.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(REPO, "tools", "build_outside_kit.py")


class OutsideKitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.out = os.path.join(cls.tmp, "dist")
        proc = subprocess.run([sys.executable, BUILD, "--out", cls.out],
                              cwd=REPO, capture_output=True, text=True,
                              timeout=120)
        assert proc.returncode == 0, proc.stderr
        cls.info = json.loads(json.dumps(dict(
            line.split(":", 1) for line in proc.stdout.strip().splitlines()
            if ":" in line)))
        cls.zip = [os.path.join(cls.out, n) for n in os.listdir(cls.out)
                   if n.endswith(".zip")][0]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_archive_carries_only_what_it_says(self):
        with zipfile.ZipFile(self.zip) as zf:
            names = [n.split("/", 1)[1] for n in zf.namelist()]
        self.assertIn("SHA256SUMS", names)
        self.assertIn("kit-manifest.json", names)
        self.assertIn("tools/outsider_audit.py", names)
        for n in names:
            self.assertFalse(n.startswith("docs/"), n)
            self.assertFalse(n.startswith("tests/test_"), n)
            self.assertNotIn("__pycache__", n)

    def test_a_stranger_unzips_and_gets_a_verdict(self):
        """No repo, no install, no network: one command, one verdict."""
        work = tempfile.mkdtemp(dir=self.tmp)
        with zipfile.ZipFile(self.zip) as zf:
            zf.extractall(work)
        root = os.path.join(work, "uibc-audit-kit")
        proc = subprocess.run([sys.executable, "tools/outsider_audit.py",
                               "--json"],
                              cwd=root, capture_output=True, text=True,
                              timeout=180)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        out = json.loads(proc.stdout)
        self.assertTrue(out["ok"])
        self.assertTrue(out["trust"]["in_repo"])
        self.assertEqual(out["stage_baseline"]["got"]["result"],
                         "INCONCLUSIVE")
        self.assertTrue(out["stage_redteam_s16"]["ok"])

    def test_an_altered_archive_is_caught(self):
        """Flip a byte in a shipped file: SHA256SUMS must notice."""
        tampered = os.path.join(self.tmp, "tampered.zip")
        with zipfile.ZipFile(self.zip) as src, \
                zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                data = src.read(item.filename)
                if item.filename.endswith("uibc_core/verify.py"):
                    data = data.replace(b"def verify(", b"def verify2(", 1)
                dst.writestr(item, data)
        proc = subprocess.run([sys.executable, BUILD, "--verify", tampered],
                              cwd=REPO, capture_output=True, text=True,
                              timeout=120)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("digest differs", proc.stdout)
        self.assertIn("verify.py", proc.stdout)

    def _extracted_root(self):
        work = tempfile.mkdtemp(dir=self.tmp)
        with zipfile.ZipFile(self.zip) as zf:
            zf.extractall(work)
        return os.path.join(work, "uibc-audit-kit")

    def test_the_kit_carries_the_declaration_tool(self):
        """An outsider who cannot declare capability cannot be compared with."""
        self.assertIn("tools/capabilities_check.py", self._names())

    def _names(self):
        with zipfile.ZipFile(self.zip) as zf:
            return [n.split("/", 1)[1] for n in zf.namelist()]

    def test_the_declaration_works_from_inside_the_kit(self):
        root = self._extracted_root()
        proc = subprocess.run([sys.executable, "tools/capabilities_check.py", "emit"],
                              cwd=root, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        decl = json.loads(proc.stdout)
        self.assertEqual(len(decl["checks"]), 20)
        with open(os.path.join(root, "uibc_core", "gate.py"), encoding="utf-8") as f:
            self.assertIn("REVOCATION_REASONS", f.read())

    def test_two_runs_of_the_audit_are_byte_identical(self):
        """One kit, one report: a second run may not say something different."""
        root = self._extracted_root()
        first = subprocess.run([sys.executable, "tools/outsider_audit.py"],
                               cwd=root, capture_output=True, text=True, timeout=180)
        second = subprocess.run([sys.executable, "tools/outsider_audit.py"],
                                cwd=root, capture_output=True, text=True, timeout=180)
        self.assertEqual(first.stdout, second.stdout)

    def test_the_report_names_no_path_on_this_machine(self):
        root = self._extracted_root()
        proc = subprocess.run([sys.executable, "tools/outsider_audit.py"],
                              cwd=root, capture_output=True, text=True, timeout=180)
        self.assertNotIn(":\\", proc.stdout)
        self.assertNotIn(REPO, proc.stdout)
        self.assertNotIn(self.tmp, proc.stdout)


if __name__ == "__main__":
    unittest.main()
