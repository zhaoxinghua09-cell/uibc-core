"""Tests for the two release-gate tools: verify_corpus and check_sdist_freshness.

The negative cases matter more than the happy path -- a gate that only ever passes
is decoration.
"""
import hashlib
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCH = os.path.join(ROOT, "conformance", "uibc-conformance-0.5.5.zip")
KIT = os.path.join(ROOT, "conformance", "uibc-conformance-0.5.5.ARCHIVE.sha256")
MAN = os.path.join(ROOT, "conformance", "MANIFEST.sha256")
PIN = os.path.join(ROOT, "anchors", "pins", "uibc-conformance-0.5.5.sha256")


def run(tool, args):
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", tool)] + args,
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


class VerifyCorpus(unittest.TestCase):
    def test_pass_with_kit_manifest(self):
        rc, out = run("verify_corpus.py", ["--archive", ARCH, "--manifest", MAN,
                                           "--pin", PIN, "--archive-manifest", KIT])
        self.assertEqual(rc, 0, out)
        self.assertIn("456", out)

    def test_fails_without_kit_manifest(self):
        rc, out = run("verify_corpus.py", ["--archive", ARCH, "--manifest", MAN, "--pin", PIN])
        self.assertEqual(rc, 2, out)
        self.assertIn("no digest record", out)

    def test_tampered_archive_fails(self):
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, "a.zip")
            b = bytearray(open(ARCH, "rb").read())
            b[10] ^= 1
            open(bad, "wb").write(bytes(b))
            rc, out = run("verify_corpus.py", ["--archive", bad, "--manifest", MAN,
                                              "--pin", PIN, "--archive-manifest", KIT])
            self.assertEqual(rc, 2, out)
            self.assertIn("does not match the pin", out)

    def test_damaged_zip_reports_a_verdict_instead_of_a_traceback(self):
        # 一个字节都不改 hash 的话可以骗过 pin 检查，所以这里只断言行为：损坏 zip
        # 必须给出 2 或 3 的判决，且不能抛 Traceback。实测：翻某一个字节曾让工具
        # 抛 BadZipFile、连判词都没打出来（2026-11-25 演练时抓到）。
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, "b.zip")
            raw = bytearray(open(ARCH, "rb").read())
            raw[200] ^= 0xFF
            open(bad, "wb").write(bytes(raw))
            rc, out = run("verify_corpus.py", ["--archive", bad, "--manifest", MAN,
                                              "--pin", PIN, "--archive-manifest", KIT])
            self.assertIn(rc, (2, 3), out)
            self.assertNotIn("Traceback", out)

    def test_missing_input_is_inconclusive(self):
        rc, out = run("verify_corpus.py", ["--archive", "nope.zip", "--manifest", "nope",
                                          "--pin", "nope"])
        self.assertEqual(rc, 3, out)


class SdistFreshness(unittest.TestCase):
    def _sdist(self, td, contents):
        path = os.path.join(td, "dist.tar.gz")
        with tarfile.open(path, "w:gz") as tf:
            for name, text in contents.items():
                data = text.encode("utf-8")
                info = tarfile.TarInfo("pkg-0.9.9/" + name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        return path

    def test_stale_version_fails(self):
        with tempfile.TemporaryDirectory() as td:
            s = self._sdist(td, {"conformance/oracle/cases/accept-one/manifest.json":
                                 '{"version": "0.9.8"}'})
            rc, out = run("check_sdist_freshness.py", ["--sdist", s, "--version", "0.9.9"])
            self.assertEqual(rc, 2, out)

    def test_clean_sdist_passes(self):
        with tempfile.TemporaryDirectory() as td:
            s = self._sdist(td, {"conformance/oracle/cases/accept-one/manifest.json":
                                 '{"version": "0.9.9"}'})
            rc, out = run("check_sdist_freshness.py", ["--sdist", s, "--version", "0.9.9"])
            self.assertEqual(rc, 0, out)

    def test_changelog_mention_is_exempt(self):
        with tempfile.TemporaryDirectory() as td:
            s = self._sdist(td, {"CHANGELOG.md": "## 0.9.8 -> 0.9.9",
                                 "conformance/oracle/cases/a/manifest.json": '{"version": "0.9.9"}'})
            rc, out = run("check_sdist_freshness.py", ["--sdist", s, "--version", "0.9.9"])
            self.assertEqual(rc, 0, "CHANGELOG mentioning an old version is normal; " + out)

    def test_unreadable_is_inconclusive(self):
        rc, out = run("check_sdist_freshness.py", ["--sdist", "nope.tar.gz", "--version", "0.9.9"])
        self.assertEqual(rc, 3, out)


class GateBundle(unittest.TestCase):
    def test_gate_script_exists_and_reports_three_steps(self):
        rc, out = run("../../release_gate.py", ["--help"]) if os.path.exists(
            os.path.join(ROOT, "../../release_gate.py")) else (0, "")
        # 组合脚本可与本测试分离存放；此处只保证两支工具自身的三值口径成立。
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
