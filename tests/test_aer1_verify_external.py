#!/usr/bin/env python3
"""Tests for the inbound path: judging somebody else's receipt.

The real corpus lives outside this repository, so the fixtures here are
built locally: one receipt of our own, plus deliberately broken inputs.
The point being pinned is that the file-level check runs before any
dict-shaped judgement can hide a duplicate member.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


external = _load("aer1_verify_external", "tools/aer1_verify_external.py")
emit = _load("emit_aer1_receipts", "tools/emit_aer1_receipts.py")


class VerifyExternalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package = os.path.join(ROOT, "fixtures", "clean.uibc")
        cls.manifest, entries = emit.load_package(package)
        cls.receipt = emit.build_receipt(cls.manifest, entries[0], 0, package, package)
        cls.tmp = tempfile.mkdtemp()

    def _write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_our_own_receipt_is_accepted(self):
        path = self._write("ok.json", json.dumps(self.receipt))
        report = external.judge(path)
        self.assertEqual(report["verdict"], "ACCEPTED")
        self.assertEqual(report["file_checks"], [])
        self.assertTrue(report["id_verdict"])

    def test_duplicate_member_is_caught_before_parsing(self):
        body = json.dumps(self.receipt)
        # A duplicate member is invisible to json.load, which keeps the last.
        broken = body[:-1] + ', "output_hash": "sha256:%s"}' % ("0" * 64)
        report = external.judge(self._write("dup.json", broken))
        self.assertEqual(report["verdict"], "REJECTED")
        self.assertTrue(any("duplicate member name: output_hash" in item
                            for item in report["file_checks"]))

    def test_non_json_is_rejected(self):
        report = external.judge(self._write("bad.json", "not json at all"))
        self.assertEqual(report["verdict"], "REJECTED")

    def test_array_is_rejected(self):
        report = external.judge(self._write("arr.json", "[]"))
        self.assertEqual(report["verdict"], "REJECTED")
        self.assertTrue(any("not a JSON object" in item
                            for item in report["file_checks"]))

    def test_tampered_receipt_is_rejected_on_the_structural_layer(self):
        receipt = dict(self.receipt)
        receipt["output_hash"] = "sha256:" + "0" * 64
        report = external.judge(self._write("tamper.json", json.dumps(receipt)))
        self.assertEqual(report["verdict"], "REJECTED")
        self.assertTrue(report["structural"])

    def test_report_names_the_three_layers(self):
        path = self._write("layers.json", json.dumps(self.receipt))
        report = external.judge(path)
        for key in ("file_checks", "structural", "binding",
                    "reference_profile", "disinterested", "anchors", "id_verdict"):
            self.assertIn(key, report)

    def test_id_verdict_is_a_verdict_not_an_error_string(self):
        # Measured 2026-11-19: the call passed one argument to a two-argument
        # function, the exception was swallowed into "error: ...", and the
        # report still printed ACCEPTED. A field that can only ever hold an
        # error string never fails, so pin the vocabulary instead.
        vocabulary = {"absent", "unverified", "matched", "resolved", "mismatched"}
        path = self._write("id.json", json.dumps(self.receipt))
        report = external.judge(path)
        self.assertIn(report["id_verdict"], vocabulary)
        self.assertNotIn("error", str(report["id_verdict"]).lower())


if __name__ == "__main__":
    unittest.main()
