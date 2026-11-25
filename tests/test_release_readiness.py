#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The release-readiness gate must be able to fail.

A check that cannot fail on the property you care about is not a check. These
tests build throw-away trees where the three properties are wrong one at a time,
and assert the gate names each of them.
"""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import check_release_readiness as rr


def make_tree(version="0.5.4", *, strings="0.5.4", archive_version="0.5.4",
              make_archive=True, archive_bytes=b"PK-ok"):
    tmp = Path(tempfile.mkdtemp())
    (tmp / "uibc_core").mkdir()
    (tmp / "pyproject.toml").write_text(
        '[project]\nname = "uibc-core"\nversion = "%s"\n' % strings, encoding="utf-8")
    (tmp / "uibc_core" / "__init__.py").write_text(
        '__version__ = "%s"\n' % strings, encoding="utf-8")
    (tmp / "server.json").write_text(json.dumps(
        {"version": strings, "packages": [{"name": "uibc-core", "version": strings}]}),
        encoding="utf-8")
    (tmp / "conformance").mkdir()
    if make_archive:
        p = tmp / "conformance" / ("uibc-conformance-%s.zip" % version)
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("MANIFEST.json", json.dumps({"version": archive_version}))
    return tmp


class ReadinessGate(unittest.TestCase):
    def setUp(self):
        self._root = rr.ROOT

    def tearDown(self):
        rr.ROOT = self._root

    def check(self, tree, version="0.5.4", tag=None):
        rr.ROOT = tree
        return rr.check(version, tag)

    def test_ready(self):
        t = make_tree()
        self.assertEqual(self.check(t, tag="v0.5.4"), [])
        self.assertEqual(rr.main.__name__, "main")

    def test_version_strings_disagree(self):
        t = make_tree(strings="0.5.3")
        problems = self.check(t)
        joined = " | ".join(problems)
        self.assertIn("pyproject.toml", joined)
        self.assertIn("__version__", joined)
        self.assertIn("server.json", joined)

    def test_archive_missing(self):
        t = make_tree(make_archive=False)
        problems = self.check(t)
        self.assertTrue(any("no archive" in p for p in problems), problems)
        self.assertTrue(any("build_conformance_bundle.py 0.5.4" in p for p in problems), problems)

    def test_archive_names_another_version(self):
        t = make_tree(archive_version="0.5.2")
        problems = self.check(t)
        self.assertTrue(any("records version" in p for p in problems), problems)

    def test_tag_mismatch(self):
        t = make_tree()
        problems = self.check(t, tag="v0.5.3")
        self.assertTrue(any("does not name version" in p for p in problems), problems)

    def test_empty_archive(self):
        t = make_tree()
        (t / "conformance" / "uibc-conformance-0.5.4.zip").write_bytes(b"")
        problems = self.check(t)
        self.assertTrue(any("is empty" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
