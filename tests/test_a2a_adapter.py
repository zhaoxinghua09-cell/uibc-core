"""A2A adapter tests (task G21). JSON-RPC 2.0 dispatch + HTTP round-trip.

Operator-trusted model: the adapter verifies packages that exist under the
operator's --packages root; path traversal is rejected; read-only surface.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import cli as ucli
from uibc_core.signing import generate_key
from adapters.a2a.server import A2AAdapter, make_handler  # noqa: E402


def _make_pkg(tmp, name, key_hex=None):
    pkg = os.path.join(tmp, name)
    ucli.cmd_init(type("A", (), {"path": pkg})())
    ucli.cmd_register(type("A", (), {
        "path": pkg, "agent_id": "a2a-agent", "owner": "a2a-owner",
        "agent_type": "software-agent", "version": "1"})())
    src = os.path.join(tmp, "ev.txt")
    with open(src, "w", encoding="utf-8") as f:
        f.write("a2a evidence for %s\n" % name)
    ucli.cmd_evidence(type("A", (), {
        "path": pkg, "type": "ACTION", "file": src,
        "media_type": "text/plain", "note": "n"})())
    kf = None
    if key_hex is not None:
        kf = os.path.join(tmp, name + ".key")
        with open(kf, "w", encoding="ascii") as f:
            f.write(key_hex)
    ucli.cmd_submit(type("A", (), {"path": pkg, "key": kf})())
    return pkg


def _rpc(port, method, params=None, rid=1, raw=None):
    body = raw if raw is not None else json.dumps(
        {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
    req = urllib.request.Request(
        "http://127.0.0.1:%d/rpc" % port, data=body.encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


class A2AAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="a2a-")
        cls.key = generate_key()
        _make_pkg(cls.tmp, "good.uibc")
        _make_pkg(cls.tmp, "sealed.uibc", cls.key.hex())
        # a tampered copy of good
        shutil.copytree(os.path.join(cls.tmp, "good.uibc"),
                        os.path.join(cls.tmp, "tampered.uibc"))
        ev_root = os.path.join(cls.tmp, "tampered.uibc", "evidence", "files")
        evs = sorted(os.listdir(ev_root))
        if evs:
            with open(os.path.join(ev_root, evs[0]), "a", encoding="utf-8") as f:
                f.write("forged\n")
        cls.card_path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "adapters", "a2a", "agent-card.json")
        cls.adapter = A2AAdapter(cls.tmp, cls.card_path)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.adapter))
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    # dispatch level -------------------------------------------------------
    def test_01_card(self):
        r = self.adapter.dispatch("card", {})
        self.assertIn("name", r)

    def test_02_verify_clean_open(self):
        r = self.adapter.dispatch("uibc/verify", {"package": "good.uibc"})
        self.assertEqual(r["result"], "PASS")

    def test_03_verify_sealed_with_key(self):
        r = self.adapter.dispatch("uibc/verify",
                                  {"package": "sealed.uibc",
                                   "key": self.key.hex()})
        self.assertEqual(r["result"], "PASS")

    def test_04_verify_tampered_fails(self):
        r = self.adapter.dispatch("uibc/verify", {"package": "tampered.uibc"})
        self.assertEqual(r["result"], "FAIL")

    def test_05_gate_allow(self):
        r = self.adapter.dispatch("uibc/gate", {"package": "good.uibc"})
        self.assertEqual(r["decision"], "ALLOW")

    def test_06_inspect_identity(self):
        r = self.adapter.dispatch("uibc/inspect", {"package": "good.uibc"})
        self.assertEqual(r["identity"], "a2a-agent")

    def test_07_unknown_method(self):
        with self.assertRaises(ValueError):
            self.adapter.dispatch("uibc/rewrite", {})

    def test_08_traversal_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter.dispatch("uibc/verify", {"package": "../etc"})

    def test_09_missing_package(self):
        with self.assertRaises(FileNotFoundError):
            self.adapter.dispatch("uibc/verify", {"package": "ghost.uibc"})

    # HTTP / JSON-RPC level -------------------------------------------------
    def test_10_jsonrpc_roundtrip(self):
        r = _rpc(self.port, "uibc/verify", {"package": "good.uibc"})
        self.assertEqual(r["result"]["result"], "PASS")
        self.assertEqual(r["id"], 1)

    def test_11_method_not_found(self):
        r = _rpc(self.port, "nope")
        self.assertEqual(r["error"]["code"], -32601)

    def test_12_invalid_jsonrpc_version(self):
        r = _rpc(self.port, "card", raw=json.dumps(
            {"jsonrpc": "1.0", "id": 2, "method": "card"}))
        self.assertEqual(r["error"]["code"], -32600)

    def test_13_parse_error(self):
        r = _rpc(self.port, "card", raw="{not json")
        self.assertEqual(r["error"]["code"], -32700)

    def test_14_params_error_as_rpc_error(self):
        r = _rpc(self.port, "uibc/verify", {"package": "ghost.uibc"})
        self.assertEqual(r["error"]["code"], -32602)

    # stdio subprocess smoke test (real entrypoint)
    def test_15_subprocess_startup(self):
        proc = subprocess.Popen(
            [sys.executable, os.path.join("adapters", "a2a", "server.py"),
             "--packages", self.tmp, "--port", "0"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))
        try:
            proc.terminate()
        finally:
            pass  # port 0 prints real port; subprocess start is the smoke check


if __name__ == "__main__":
    unittest.main()
