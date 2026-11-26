# -*- coding: utf-8 -*-
"""The node hook, exercised against a stub: the one branch that needs a real node.

No Bitcoin Core is installed on this machine, so the honest thing is not to
delete the branch - it is to run it against a JSON-RPC double and say exactly
what that proves: the wiring (method names, auth shape, field names, the
disagree and unreachable paths) is exercised; the node's *answer* is not
authenticated by anything here.
"""
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import ots_block_crosscheck as cc  # noqa: E402

BLOCK_HASH = "00000000000000000001b9b568f25bb0dbb631c3084632a22135c3bfcb0f11a7"


class StubCore(BaseHTTPRequestHandler):
    results = {}
    calls = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length).decode())
        method = req.get("method")
        StubCore.calls.append(method)
        value = StubCore.results.get(method)
        if isinstance(value, Exception):
            payload = {"result": None, "error": {"code": -1, "message": str(value)}}
        else:
            payload = {"result": value, "error": None, "id": req.get("id")}
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the test output clean
        pass


def _serve(results):
    StubCore.results = results
    StubCore.calls = []
    server = HTTPServer(("127.0.0.1", 0), StubCore)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://127.0.0.1:%d" % server.server_port


class NodeEvidenceTests(unittest.TestCase):
    def test_an_agreeing_node_is_recorded(self):
        server, url = _serve({
            "getblockhash": BLOCK_HASH,
            "getblockheader": {"confirmations": 160, "chainwork": "ab" * 8, "height": 977449},
            "getblockchaininfo": {"blocks": 977609, "chain": "main"},
        })
        try:
            ev = cc.node_block_evidence(url, 977449, BLOCK_HASH)
        finally:
            server.shutdown()
        self.assertTrue(ev["checked"])
        self.assertTrue(ev["hash_matches_explorers"])
        self.assertEqual(ev["confirmations"], 160)
        self.assertEqual(ev["node_height"], 977609)
        self.assertEqual(StubCore.calls, ["getblockhash", "getblockheader", "getblockchaininfo"])

    def test_a_disagreeing_node_is_named_not_smoothed_over(self):
        server, url = _serve({
            "getblockhash": "00" * 32,
            "getblockheader": {"confirmations": 1, "chainwork": "00"},
            "getblockchaininfo": {"blocks": 977609, "chain": "main"},
        })
        try:
            ev = cc.node_block_evidence(url, 977449, BLOCK_HASH)
        finally:
            server.shutdown()
        self.assertTrue(ev["checked"])
        self.assertFalse(ev["hash_matches_explorers"],
                         "a node that names a different block at this height must be visible")

    def test_an_unreachable_node_is_unchecked_not_a_pass(self):
        server, url = _serve({"getblockhash": RuntimeError("boom")})
        try:
            ev = cc.node_block_evidence(url, 977449, BLOCK_HASH)
        finally:
            server.shutdown()
        self.assertFalse(ev["checked"])
        self.assertIn("most-work", ev["reason"],
                      "an unanswered question has to stay a question")

    def test_no_node_supplied_says_so(self):
        ev = cc.node_block_evidence(None, 977449, BLOCK_HASH)
        self.assertFalse(ev["checked"])
        self.assertIn("no node configured", ev["reason"])


if __name__ == "__main__":
    unittest.main()
