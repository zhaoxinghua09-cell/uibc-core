#!/usr/bin/env python3
"""Tests for the OpenTimestamps anchoring client.

A local HTTP server stands in for a calendar. That is the honest way to test
the wire contract: it asserts the exact bytes we post, and it does not
require anyone to publish a hash to a public calendar to run CI.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


anchor_mod = _load(os.path.join(ROOT, "tools", "anchor_chain_head.py"), "anchor_chain_head")

# Not hand-made: this file is a real DetachedTimestampFile serialization
# produced by the reference implementation (python-opentimestamps,
# DetachedTimestampFile over OpSHA256 with a BitcoinBlockHeaderAttestation).
# Using it means our magic check is validated against the actual wire format,
# not against our own guess at it.
SAMPLE = os.path.join(ROOT, "tests", "data", "ots-format-sample.ots")
with open(SAMPLE, "rb") as _stream:
    FAKE_PROOF = _stream.read()


class _Handler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _Handler.received.append((self.path, body))
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        self.wfile.write(FAKE_PROOF)

    def log_message(self, *args):
        pass


class AnchorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        _Handler.received = []
        self.tmp = tempfile.mkdtemp()
        self.pkg = os.path.join(self.tmp, "pkg.uibc")
        shutil.copytree(os.path.join(ROOT, "fixtures", "clean.uibc"), self.pkg)
        self.out = os.path.join(self.tmp, "anchors")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_root_is_read_from_manifest(self):
        root = anchor_mod.package_root(self.pkg)
        with open(os.path.join(self.pkg, "manifest.json"), encoding="utf-8") as stream:
            manifest = json.load(stream)
        self.assertEqual(root, manifest["evidence_root"].lower())
        self.assertEqual(len(anchor_mod.digest_bytes(root)), 32)

    def test_dry_run_does_not_touch_the_network(self):
        # An unroutable host: if dry-run tried to post, this would fail.
        report = anchor_mod.anchor(self.pkg, calendars=["http://10.255.255.1:9"],
                                   out_dir=self.out, do_submit=False, timeout=1)
        self.assertEqual(report["state"], "dry-run")
        self.assertTrue(report["ok"])
        self.assertEqual(_Handler.received, [])

    def test_post_body_is_exactly_the_32_byte_root(self):
        report = anchor_mod.anchor(self.pkg, calendars=[self.base],
                                   out_dir=self.out, do_submit=True)
        self.assertTrue(report["ok"], report)
        self.assertEqual(len(_Handler.received), 1)
        path, body = _Handler.received[0]
        self.assertEqual(path, "/digests")
        self.assertEqual(body, bytes.fromhex(report["evidence_root"]))
        self.assertEqual(len(body), 32)

    def test_proof_is_written_with_magic_and_recorded(self):
        report = anchor_mod.anchor(self.pkg, calendars=[self.base],
                                   out_dir=self.out, do_submit=True)
        proof = report["calendars"][0]["proof_path"]
        self.assertTrue(os.path.isfile(proof))
        self.assertTrue(report["calendars"][0]["ots_magic"])
        with open(proof, "rb") as stream:
            self.assertTrue(stream.read().startswith(anchor_mod.OTS_MAGIC))
        with open(report["record_path"], encoding="utf-8") as stream:
            record = json.load(stream)
        self.assertEqual(record["evidence_root"], report["evidence_root"])
        self.assertEqual(record["state"], "pending")

    def test_leaf_calendar_failure_does_not_lose_other_proofs(self):
        report = anchor_mod.anchor(self.pkg,
                                   calendars=["http://127.0.0.1:9", self.base],
                                   out_dir=self.out, do_submit=True, timeout=2)
        self.assertFalse(report["ok"])
        statuses = [c["status"] for c in report["calendars"]]
        self.assertEqual(statuses, ["failed", "submitted"])
        self.assertTrue(os.path.isfile(report["calendars"][1]["proof_path"]))

    def test_refuses_to_write_proofs_inside_the_package(self):
        with self.assertRaises(ValueError):
            anchor_mod.anchor(self.pkg, calendars=[self.base],
                              out_dir=os.path.join(self.pkg, "anchors"),
                              do_submit=True)

    def test_magic_matches_a_real_serialized_proof(self):
        with open(SAMPLE, "rb") as stream:
            data = stream.read()
        self.assertTrue(data.startswith(anchor_mod.OTS_MAGIC))
        self.assertEqual(len(anchor_mod.OTS_MAGIC), 31)
        # Flip one header byte *away from* its current value (byte 0 is already
        # 0x00, so replacing it with 0x00 would be a no-op that proves nothing).
        tampered = data[:1] + b"P" + data[2:]
        self.assertFalse(tampered.startswith(anchor_mod.OTS_MAGIC))

    def test_manifest_without_root_is_rejected(self):
        bad = os.path.join(self.tmp, "bad.uibc")
        os.makedirs(bad)
        with open(os.path.join(bad, "manifest.json"), "w", encoding="utf-8") as stream:
            json.dump({"schema": "x"}, stream)
        with self.assertRaises(ValueError):
            anchor_mod.package_root(bad)


if __name__ == "__main__":
    unittest.main()
