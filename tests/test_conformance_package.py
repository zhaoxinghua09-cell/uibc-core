#!/usr/bin/env python3
"""The downloadable conformance package must stay self-consistent.

These tests exist because the package is shipped to strangers: a stale
MANIFEST.sha256, an archive that no longer matches its pin, or a coverage table
that disagrees with the manifest are all silent failures — the suite would still
run green while the published bytes were wrong.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CONF = os.path.join(ROOT, "conformance")
sys.path.insert(0, os.path.join(ROOT, "tools"))


class TestConformancePackage(unittest.TestCase):
    def test_manifest_matches_tree(self):
        out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_conformance_manifest.py"),
                              "--check"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_coverage_is_consistent(self):
        import importlib
        mod = importlib.import_module("check_vector_package")
        self.assertEqual(mod.check_coverage(), [])

    def test_uncovered_checks_are_named_with_reasons(self):
        doc = json.load(open(os.path.join(CONF, "coverage.json"), encoding="utf-8"))
        manifest = json.load(open(os.path.join(CONF, "manifest.json"), encoding="utf-8"))
        used = {ch for c in manifest["cases"] for ch in c.get("expected_checks", [])}
        for row in doc["uncovered"]:
            self.assertNotIn(row["id"], used, "check %s is listed uncovered but a case exercises it" % row["id"])
            self.assertTrue(row["reason"].strip(), "uncovered check %s has no reason" % row["id"])

    def test_archive_pin_recorded(self):
        import importlib
        mod = importlib.import_module("check_vector_package")
        self.assertEqual(mod.check_archive(), [], "the shipped archive no longer matches its published pin")


if __name__ == "__main__":
    unittest.main()
