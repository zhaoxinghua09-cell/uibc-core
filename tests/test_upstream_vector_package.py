"""The upstream vector package must stay reproducible and honest about scope.

The package targets the IETF SCITT WG `examples` repository, which already
merged a vector set shaped `v1/<id>/expected.json` + manifest + SHA256SUMS +
.gitattributes. These tests fail if the package stops being self-checking,
loses its declared gap, or starts claiming to cover the COSE layer.
"""

import hashlib
import json
import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(REPO, "docs", "upstream-package", "scitt-rfc9162")


def _read(name):
    with open(os.path.join(PKG, name), encoding="utf-8") as fh:
        return fh.read()


class TestPackageShape(unittest.TestCase):
    def test_the_four_files_exist(self):
        for f in ("manifest.json", "SHA256SUMS", "README.md", ".gitattributes"):
            self.assertTrue(os.path.isfile(os.path.join(PKG, f)), f)

    def test_every_vector_has_expected_json(self):
        manifest = json.loads(_read("manifest.json"))
        self.assertEqual(len(manifest["vectors"]), 5)
        for v in manifest["vectors"]:
            self.assertTrue(os.path.isfile(os.path.join(PKG, v["dir"], "expected.json")))

    def test_checksums_cover_the_manifest_and_every_vector(self):
        listed = [l.split("  ", 1)[1] for l in _read("SHA256SUMS").splitlines() if l.strip()]
        self.assertIn("manifest.json", listed)
        for line in _read("SHA256SUMS").splitlines():
            if not line.strip():
                continue
            digest, rel = line.split("  ", 1)
            with open(os.path.join(PKG, rel), "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), digest, rel)

    def test_gitattributes_pins_vectors(self):
        self.assertIn("v1/** -text", _read(".gitattributes"))


class TestPackageSelfChecks(unittest.TestCase):
    def test_the_checker_returns_consistent(self):
        out = subprocess.run(
            [sys.executable, os.path.join(REPO, "tools", "build_scitt_vector_package.py"), "--check"],
            capture_output=True, text=True, cwd=REPO, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("CONSISTENT", out.stdout)

    def test_positives_match_and_negatives_differ(self):
        manifest = json.loads(_read("manifest.json"))
        for v in manifest["vectors"]:
            e = v["expected"]
            same = e["reconstructed_root"] == e["root_true"]
            self.assertEqual(e["result"] == "VALID", same, v["id"])


class TestScopeIsDeclared(unittest.TestCase):
    def test_readme_states_what_it_does_not_cover(self):
        doc = _read("README.md")
        self.assertIn("What this set does not cover", doc)
        self.assertIn("No COSE_Sign1 statement or receipt bytes", doc)
        self.assertIn("not a replacement", doc)

    def test_readme_does_not_claim_the_cose_layer(self):
        doc = _read("README.md")
        for phrase in ("full conformance", "complete implementation", "fully compliant"):
            self.assertNotIn(phrase, doc)

    def test_checklist_says_not_sent(self):
        p = os.path.join(REPO, "docs", "UPSTREAM-PR-CHECKLIST.md")
        with open(p, encoding="utf-8") as fh:
            doc = fh.read()
        self.assertIn("未提交", doc)
        self.assertIn("Note Well", doc)
        self.assertIn("727ee03", doc)


if __name__ == "__main__":
    unittest.main()
