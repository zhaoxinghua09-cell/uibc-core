"""D-002: the index-metadata commitment must cover evidence_id, media_type, created_at.

These tests reproduce the conformance-vector defect on the old field and show the
new one closing it, without touching any package sealed before 0.6.0.

    python -m pytest tests/test_index_full_digest.py -q
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.canonical import index_full_digest, index_metadata_digest  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _entries(evidence_id="ev-1", media_type="text/plain", created_at="2026-11-20T00:00:00Z"):
    return {"entries": [{
        "path": "files/report.txt",
        "type": "OUTPUT",
        "note": "reviewed and approved",
        "content_hash": "sha256:" + "0" * 64,
        "evidence_id": evidence_id,
        "media_type": media_type,
        "created_at": created_at,
    }]}


class TestScope(unittest.TestCase):
    def test_old_digest_ignores_the_three_fields(self):
        base = index_metadata_digest(_entries())
        for kwargs in ({"evidence_id": "ev-2"},
                       {"media_type": "application/pdf"},
                       {"created_at": "2020-01-01T00:00:00Z"}):
            self.assertEqual(index_metadata_digest(_entries(**kwargs)), base,
                             "S7 scope is expected to miss %s - that is D-002" % kwargs)

    def test_new_digest_sees_each_of_them(self):
        base = index_full_digest(_entries())
        for kwargs in ({"evidence_id": "ev-2"},
                       {"media_type": "application/pdf"},
                       {"created_at": "2020-01-01T00:00:00Z"}):
            self.assertNotEqual(index_full_digest(_entries(**kwargs)), base,
                                "S20 must notice %s" % kwargs)

    def test_new_digest_is_order_independent(self):
        a = {"entries": [{"path": "b.txt", "evidence_id": "1"},
                         {"path": "a.txt", "evidence_id": "2"}]}
        b = {"entries": list(reversed(a["entries"]))}
        self.assertEqual(index_full_digest(a), index_full_digest(b))


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="uibc-s20-")
        self.pkg = os.path.join(self.tmp, "pkg")
        self._cli("init", self.pkg)
        self._cli("register", self.pkg, "--agent-id", "s20-agent", "--owner", "Test Owner")
        src = os.path.join(self.tmp, "report.txt")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("the artefact under test\n")
        self._cli("evidence", self.pkg, "--file", src, "--type", "OUTPUT",
                  "--note", "reviewed and approved")
        key = os.path.join(self.tmp, "owner.key")
        self._cli("keygen", "--out", key, "--ed25519")
        self._cli("submit", self.pkg, "--key", key)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cli(self, *args):
        p = subprocess.run([sys.executable, "-m", "uibc_core.cli", *args],
                           capture_output=True, text=True, cwd=ROOT,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        if p.returncode != 0:
            raise AssertionError("cli %s failed: %s%s" % (args, p.stdout, p.stderr))
        return p.stdout

    def _verify(self):
        p = subprocess.run([sys.executable, "-m", "uibc_core.cli", "verify", self.pkg],
                           capture_output=True, text=True, cwd=ROOT,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        return json.loads(p.stdout)

    def _check(self, report, cid):
        for c in report["checks"]:
            if c["id"] == cid:
                return c
        raise AssertionError("check %s missing from report" % cid)

    def test_sealed_package_carries_the_full_digest(self):
        with open(os.path.join(self.pkg, "manifest.json"), encoding="utf-8") as fh:
            m = json.load(fh)
        self.assertIn("evidence_index_full_digest", m)
        self.assertTrue(m["evidence_index_full_digest"].startswith("sha256:"))

    def test_honest_package_passes_both_checks(self):
        r = self._verify()
        self.assertEqual(r["result"], "PASS")
        self.assertEqual(self._check(r, "S7")["result"], "PASS")
        self.assertEqual(self._check(r, "S20")["result"], "PASS")

    def test_backdating_is_caught_and_only_by_s20(self):
        idx_path = os.path.join(self.pkg, "evidence", "index.json")
        with open(idx_path, encoding="utf-8") as fh:
            idx = json.load(fh)
        idx["entries"][0]["created_at"] = "2020-01-01T00:00:00Z"
        idx["entries"][0]["evidence_id"] = "ev-swapped"
        with open(idx_path, "w", encoding="utf-8") as fh:
            json.dump(idx, fh, indent=2)

        r = self._verify()
        self.assertEqual(r["result"], "FAIL",
                         "a rewritten evidence_id/created_at must not verify PASS")
        self.assertEqual(self._check(r, "S20")["result"], "FAIL")
        # The narrow check still passes: that is the whole point of D-002, and
        # the reason S20 exists as a second commitment rather than a widened one.
        self.assertEqual(self._check(r, "S7")["result"], "PASS")


class TestBackwardCompatibility(unittest.TestCase):
    """A package sealed before 0.6.0 carries no full digest. It must still verify,
    and it must say out loud that its coverage is partial - never pass silently
    as if the gap were closed."""

    def test_pre_060_fixture_verifies_with_partial_note(self):
        pkg = os.path.join(ROOT, "fixtures", "clean.uibc")
        if not os.path.isdir(pkg):
            self.skipTest("no pre-0.6.0 fixture checked in")
        with open(os.path.join(pkg, "manifest.json"), encoding="utf-8") as fh:
            m = json.load(fh)
        if "evidence_index_full_digest" in m:
            self.skipTest("fixture has been resealed with 0.6.0")
        p = subprocess.run([sys.executable, "-m", "uibc_core.cli", "verify", pkg],
                           capture_output=True, text=True, cwd=ROOT,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        r = json.loads(p.stdout)
        s20 = next(c for c in r["checks"] if c["id"] == "S20")
        self.assertEqual(s20["result"], "PASS")
        self.assertIn("partial coverage", s20["detail"])


if __name__ == "__main__":
    unittest.main()
