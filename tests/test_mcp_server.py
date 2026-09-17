"""MCP server tests: protocol surface + each read-only tool on real packages."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from mcp_server.server import handle, TOOLS, TOOL_FUNCS  # noqa: E402
from uibc_core.cli import main as cli_main  # noqa: E402


def _run_cli(*argv):
    sys.argv = ["uibc"] + list(argv)
    try:
        cli_main()
    except SystemExit as e:
        if e.code not in (0, None):
            raise


class McpServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="mcp-test-")
        cls.pkg = os.path.join(cls.tmp, "demo")
        os.makedirs(cls.tmp, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(cls.tmp)
        try:
            _run_cli("init", "demo")
            _run_cli("register", "demo", "--agent-id", "mcp-agent", "--owner", "tester")
            with open("log.txt", "w", encoding="utf-8") as f:
                f.write("evidence line\n")
            _run_cli("evidence", "demo", "--type", "ACTION", "--file", "log.txt")
            _run_cli("submit", "demo")
        finally:
            os.chdir(cwd)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _call(self, name, arguments):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": name, "arguments": arguments}}
        resp = handle(msg)
        return json.loads(resp["result"]["content"][0]["text"])

    # 1. initialize handshake
    def test_01_initialize(self):
        r = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(r["result"]["serverInfo"]["name"], "uibc-core")
        self.assertIn("protocolVersion", r["result"])

    # 2. tools/list exposes 7 read-only tools with schemas
    def test_02_tools_list(self):
        r = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = {t["name"] for t in r["result"]["tools"]}
        self.assertEqual(names, set(TOOL_FUNCS))
        for t in r["result"]["tools"]:
            self.assertIn("inputSchema", t)

    # 3. read-only guarantee: no tool mutates a package (checksum before/after)
    def test_03_read_only_no_mutation(self):
        import hashlib
        def snapshot():
            state = {}
            for root, _, files in os.walk(self.pkg):
                for f in files:
                    p = os.path.join(root, f)
                    with open(p, "rb") as fh:
                        state[p] = hashlib.sha256(fh.read()).hexdigest()
            return state
        before = snapshot()
        for name in ("verify_package", "gate_check", "inspect_package",
                     "get_identity", "list_events", "list_evidence"):
            self._call(name, {"path": self.pkg})
        self.assertEqual(before, snapshot())

    # 4. verify_package PASS on the clean sealed package
    def test_04_verify_pass(self):
        r = self._call("verify_package", {"path": self.pkg})
        self.assertEqual(r["result"], "PASS")

    # 5. verify_package FAIL on a tampered copy
    def test_05_verify_tamper_fail(self):
        bad = os.path.join(self.tmp, "bad")
        shutil.copytree(self.pkg, bad)
        ev_dir = os.path.join(bad, "evidence", "files")
        victim = os.listdir(ev_dir)[0]
        with open(os.path.join(ev_dir, victim), "a", encoding="utf-8") as f:
            f.write("tampered\n")
        r = self._call("verify_package", {"path": bad})
        self.assertEqual(r["result"], "FAIL")

    # 6. gate_check returns a decision with exit_code
    def test_06_gate_allow(self):
        r = self._call("gate_check", {"path": self.pkg})
        self.assertEqual(r["decision"], "ALLOW")
        self.assertEqual(r["exit_code"], 0)

    # 7. inspect_package fields
    def test_07_inspect(self):
        r = self._call("inspect_package", {"path": self.pkg})
        self.assertEqual(r["agent_id"], "mcp-agent")
        self.assertEqual(r["evidence_count"], 1)

    # 8. get_identity / list_events / list_evidence
    def test_08_reads(self):
        self.assertEqual(self._call("get_identity", {"path": self.pkg})["agent_id"], "mcp-agent")
        ev = self._call("list_events", {"path": self.pkg})["events"]
        self.assertEqual(ev[0]["event_type"], "REGISTER")
        idx = self._call("list_evidence", {"path": self.pkg})
        self.assertEqual(len(idx["entries"]), 1)
        self.assertIn("content_hash", idx["entries"][0])

    # 9. unknown tool -> JSON-RPC error
    def test_09_unknown_tool(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "write_something", "arguments": {}}}
        self.assertIn("error", handle(msg))

    # 10. notifications produce no response
    def test_10_notification_silent(self):
        self.assertIsNone(handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    # 11. subprocess smoke test: real stdio round-trip
    def test_11_stdio_roundtrip(self):
        env = dict(os.environ)
        init = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
        call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "verify_package", "arguments": {"path": self.pkg}}}
        payload = "\n".join(json.dumps(m) for m in (init, call)) + "\n"
        proc = subprocess.run(
            [sys.executable, "-m", "mcp_server.server"],
            input=payload, capture_output=True, text=True, cwd=REPO, env=env,
            timeout=60)
        lines = [json.loads(l) for l in proc.stdout.strip().splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)
        verify_resp = json.loads(lines[1]["result"]["content"][0]["text"])
        self.assertEqual(verify_resp["result"], "PASS")


if __name__ == "__main__":
    unittest.main()
