"""The upstream vector package must stay reproducible and honest about scope.

The package targets the IETF SCITT WG `examples` repository, which already
merged a vector set shaped `v1/<id>/expected.json` + manifest + SHA256SUMS +
.gitattributes. These tests fail if the package stops being self-checking,
loses its declared gap, or starts claiming to cover the COSE layer.
"""

import hashlib
import json
import os
import shutil
import tempfile
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
        # The manifest must list exactly the cases the builder knows about. This used
        # to be a hard-coded 6, which hid the real defect: the committed manifest had
        # 6 while the builder knew 5, so a plain `build` run would have dropped a
        # vector from the manifest and left its directory orphaned.
        sys.path.insert(0, REPO)
        from tools.build_scitt_vector_package import CASES, CONSISTENCY_CASES
        known = [c[0] for c in CASES] + [c[0] for c in CONSISTENCY_CASES]
        self.assertEqual(len(manifest["vectors"]), len(known))
        self.assertGreaterEqual(len(known), 25, "the corpus shrank without anyone saying so")
        for v in manifest["vectors"]:
            self.assertTrue(os.path.isfile(os.path.join(PKG, v["dir"], "expected.json")))
        self.assertEqual(sorted(v["id"] for v in manifest["vectors"]), sorted(known))

    def test_package_bytes_are_line_ending_independent(self):
        # Build wrote its files through text mode without newline="\n" until
        # 2026-11-20, which means Windows produced CRLF and Linux produced LF from
        # the same script. The committed blob was CRLF, so --check-drift passed on
        # Windows and failed on every Linux CI runner. A "reproducible on any
        # platform" package cannot have platform-dependent bytes, so this pins LF.
        for root, _dirs, files in os.walk(PKG):
            for f in files:
                p = os.path.join(root, f)
                with open(p, "rb") as fh:
                    self.assertNotIn(b"\r", fh.read(), os.path.relpath(p, PKG))

    def test_committed_bytes_are_what_the_builder_produces(self):
        out = subprocess.run(
            [sys.executable, os.path.join(REPO, "tools", "build_scitt_vector_package.py"),
             "--check-drift"],
            capture_output=True, text=True, cwd=REPO, timeout=180)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("CONSISTENT", out.stdout)

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

    def test_a_negative_without_a_positive_twin_is_a_finding(self):
        # Drop the positive at 5,0 at runtime: fail-path-swap-tree5 is then the only
        # vector at that shape, and an implementation that refuses everything there
        # would pass it. The builder's invariant must say so rather than stay green.
        import tools.build_scitt_vector_package as b
        orig = b.CASES
        tmp = tempfile.mkdtemp(prefix="scitt-pair-")
        try:
            b.CASES = [c for c in orig if c[0] != "valid-tree5-index0"]
            b.build(tmp)
            ok, msgs = b.verify(tmp)
        finally:
            b.CASES = orig
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertFalse(ok, msgs)
        self.assertTrue(any("no positive twin" in m for m in msgs), msgs)

    def test_an_unknown_result_word_is_a_finding(self):
        import tools.build_scitt_vector_package as b
        tmp = tempfile.mkdtemp(prefix="scitt-vocab-")
        try:
            b.build(tmp)
            path = os.path.join(tmp, "v1", "fail-path-swap", "expected.json")
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            doc["result"] = "INVALID_SOMETHING_WE_JUST_MADE_UP"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
            ok, msgs = b.verify(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertFalse(ok, msgs)
        self.assertTrue(any("outside the package's refusal vocabulary" in m for m in msgs), msgs)

    def test_a_refusal_word_no_vector_claims_is_a_finding(self):
        # A word in the vocabulary with no instance behind it is a claim, not a check.
        import tools.build_scitt_vector_package as b
        tmp = tempfile.mkdtemp(prefix="scitt-vocab2-")
        orig = b.RESULT_VOCAB
        try:
            b.RESULT_VOCAB = orig + ("INVALID_FRESHNESS",)
            b.build(tmp)
            ok, msgs = b.verify(tmp)
        finally:
            b.RESULT_VOCAB = orig
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertFalse(ok, msgs)
        self.assertTrue(any("no vector ever claims" in m for m in msgs), msgs)

    def test_the_algebra_agrees_on_every_shape_up_to_a_bound(self):
        # The 55 vectors are chosen shapes; this sweeps all of them up to 16 with
        # a self-test that must catch two mutations, so the sweep is alive in CI
        # at a size where it costs nothing. The 64/128 runs live in the workflow.
        out = subprocess.run(
            [sys.executable, os.path.join(REPO, "tools",
                                          "verify_tree_algebra_exhaustive.py"),
             "--max-size", "16", "--self-test"],
            capture_output=True, text=True, cwd=REPO, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("SWEEP-AGREES", out.stdout)
        self.assertIn("self-test caught", out.stdout)

    def test_positives_match_and_negatives_differ(self):
        manifest = json.loads(_read("manifest.json"))
        for v in manifest["vectors"]:
            e = v["expected"]
            if v.get("kind") == "consistency":
                same = (e["reconstructed_old_root"] == e["old_root"]
                        and e["reconstructed_new_root"] == e["new_root"])
            else:
                same = e["reconstructed_root"] == e["root_true"]
            ok = e["result"] == "VALID" or e["result"].endswith("_UNAUTHENTICATED")
            self.assertEqual(ok, same, v["id"])


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

