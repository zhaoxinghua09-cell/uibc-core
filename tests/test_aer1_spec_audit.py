#!/usr/bin/env python3
"""Tests for the static AER-1 corpus audit.

The audit is a counting tool, so the tests build a tiny corpus with known
counts and assert the tool reports exactly those. No dependency on the
143-vector kit: CI must be able to check the checker.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit_mod = _load(os.path.join(ROOT, "tools", "aer1_spec_audit.py"), "aer1_spec_audit")


def _write(path, obj, raw=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if raw is not None:
        with open(path, "wb") as stream:
            stream.write(raw)
        return
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(obj, stream)


class SpecAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.kit = os.path.join(self.tmp, "kit")
        base = os.path.join(self.kit, "base")
        vectors = os.path.join(base, "test-vectors")
        # valid: one 0.4 without metadata_hash, one 0.4 with it, one 0.3
        _write(os.path.join(vectors, "valid", "a.json"),
               {"receipt_schema_version": "0.4"})
        _write(os.path.join(vectors, "valid", "b.json"),
               {"receipt_schema_version": "0.4", "metadata_hash": "sha256:x"})
        _write(os.path.join(vectors, "valid", "c.json"),
               {"receipt_schema_version": "0.3"})
        # invalid: one 0.4 without metadata_hash
        _write(os.path.join(vectors, "invalid", "d.json"),
               {"receipt_schema_version": "0.4"})
        # one valid file ending in a newline
        _write(os.path.join(vectors, "valid", "e.json"),
               {"receipt_schema_version": "0.3"}, raw=b'{"x":1}\n')
        # base vectors: seq float (valid) and entry_count float (invalid)
        _write(os.path.join(base, "chain-vectors.json"), {"vectors": [
            {"name": "seq-float", "expected_verdict": "valid",
             "timeline": [{"seq": 1.0}, {"seq": 2.0}]}]})
        _write(os.path.join(base, "commitment-vectors.json"), {"vectors": [
            {"name": "entry-count-float", "expected_verdict": "invalid",
             "commitment": {"entry_count": 5.0}}]})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_metadata_hash_counts(self):
        report = audit_mod.audit(self.kit)
        finding = next(f for f in report["findings"] if f["id"] == "A")
        valid = finding["detail"]["valid"]
        self.assertEqual(valid["schema_0_4"], 2)
        self.assertEqual(valid["missing_metadata_hash"], 1)
        self.assertEqual(valid["files"], ["a.json"])
        self.assertEqual(finding["detail"]["invalid"]["missing_metadata_hash"], 1)
        self.assertEqual(finding["status"], "conflict")

    def test_integer_float_vectors_are_reported_with_their_verdicts(self):
        report = audit_mod.audit(self.kit)
        finding = next(f for f in report["findings"] if f["id"] == "B")
        vectors = finding["detail"]["vectors"]
        self.assertEqual(len(vectors), 2)
        by_name = {v["name"]: v for v in vectors}
        self.assertEqual(by_name["seq-float"]["expected_verdict"], "valid")
        self.assertEqual(by_name["entry-count-float"]["expected_verdict"], "invalid")
        self.assertEqual(finding["status"], "ambiguous")

    def test_newline_count_is_reported_and_not_called_a_violation(self):
        report = audit_mod.audit(self.kit)
        finding = next(f for f in report["findings"] if f["id"] == "C")
        self.assertEqual(finding["status"], "withdrawn")
        self.assertEqual(finding["detail"]["valid"]["ending_with_newline"], 1)
        self.assertIn("none", finding["detail"]["spec_clause"])

    def test_missing_kit_is_an_error_not_a_crash(self):
        with self.assertRaises(FileNotFoundError):
            audit_mod.audit(os.path.join(self.tmp, "nope"))


if __name__ == "__main__":
    unittest.main()
