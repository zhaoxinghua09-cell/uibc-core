#!/usr/bin/env python3
"""Tests for the single-command interop demo.

The demo itself needs the publisher's runner, which is external. What is
pinned here is the part that must not silently drift: the tampering set
is exactly the eight cases the result document lists, in that order.
If someone edits the demo to drop a case, the published table would
stop matching the code that produces it.
"""

import base64
import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


demo = _load("aer1_interop_demo", "tools/aer1_interop_demo.py")
emit = _load("emit_aer1_receipts", "tools/emit_aer1_receipts.py")

EXPECTED = [
    "untouched",
    "flip one payload byte",
    "wrong output_hash",
    "relabel provenance",
    "impossible date",
    "drop metadata_hash",
    "non-canonical base64 pad bit",
    "id with trailing newline",
]


class InteropDemoTest(unittest.TestCase):
    def setUp(self):
        package = os.path.join(ROOT, "fixtures", "clean.uibc")
        manifest, entries = emit.load_package(package)
        self.receipt = emit.build_receipt(manifest, entries[0], 0, package, package)

    def test_tampering_set_is_the_documented_eight(self):
        names = [name for name, _ in demo.tamperings(self.receipt)]
        self.assertEqual(names, EXPECTED)

    def test_each_case_is_a_distinct_receipt(self):
        cases = demo.tamperings(self.receipt)
        blobs = [json.dumps(receipt, sort_keys=True) for _, receipt in cases]
        self.assertEqual(len(set(blobs)), len(cases))

    def test_untouched_case_leaves_the_receipt_intact(self):
        cases = dict(demo.tamperings(self.receipt))
        self.assertEqual(cases["untouched"], self.receipt)

    def test_tampering_does_not_mutate_the_input(self):
        before = json.dumps(self.receipt, sort_keys=True)
        demo.tamperings(self.receipt)
        self.assertEqual(json.dumps(self.receipt, sort_keys=True), before)

    def test_only_the_metadata_case_touches_metadata_hash(self):
        cases = dict(demo.tamperings(self.receipt))
        self.assertNotIn("metadata_hash", cases["drop metadata_hash"])
        for name, receipt in cases.items():
            if name != "drop metadata_hash":
                self.assertIn("metadata_hash", receipt)


if __name__ == "__main__":
    unittest.main()
