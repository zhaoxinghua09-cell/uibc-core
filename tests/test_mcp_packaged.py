"""Packaged MCP server tests: uibc_core.mcp_server (the pip-installed path).

The repo-layout server is covered by tests/test_mcp_server.py via the
mcp_server shim. This file pins the packaged module's surface and the
v0.3 pubkey-pinning behaviour of its verify_package tool, including the
negative control: a wrong pinned key must FAIL at S6.
"""

import base64
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from uibc_core.mcp_server import handle, TOOLS, TOOL_FUNCS  # noqa: E402
from uibc_core.cli import main as cli_main  # noqa: E402


def _run_cli(*argv):
    sys.argv = ["uibc"] + list(argv)
    try:
        cli_main()
    except SystemExit as e:
        if e.code not in (0, None):
            raise


class McpPackagedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="mcp-packaged-test-")
        cls.pkg = os.path.join(cls.tmp, "demo")
        cwd = os.getcwd()
        os.chdir(cls.tmp)
        try:
            _run_cli("init", "demo")
            _run_cli("register", "demo", "--agent-id", "mcp-agent", "--owner", "tester")
            with open("log.txt", "w", encoding="utf-8") as f:
                f.write("evidence line\n")
            _run_cli("evidence", "demo", "--type", "ACTION", "--file", "log.txt")
            _run_cli("keygen", "--ed25519", "--out", "owner.key")
            _run_cli("submit", "demo", "--key", "owner.key")
        finally:
            os.chdir(cwd)
        with open(os.path.join(cls.pkg, "signatures", "seal.json"),
                  encoding="utf-8") as f:
            seal = json.load(f)
        cls.pubkey_hex = base64.b64decode(seal["public_key"]).hex()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _call(self, name, arguments):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": name, "arguments": arguments}}
        resp = handle(msg)
        return json.loads(resp["result"]["content"][0]["text"])

    def test_01_tools_surface_matches(self):
        names = {t["name"] for t in TOOLS}
        self.assertEqual(names, set(TOOL_FUNCS))
        self.assertEqual(len(names), 7)

    def test_02_verify_open_pass(self):
        r = self._call("verify_package", {"path": self.pkg})
        self.assertEqual(r["result"], "PASS")

    def test_03_verify_correct_pubkey_pass(self):
        r = self._call("verify_package",
                       {"path": self.pkg, "pubkey_hex": self.pubkey_hex})
        self.assertEqual(r["result"], "PASS")

    def test_04_verify_wrong_pubkey_fails_s6(self):
        wrong = bytearray(bytes.fromhex(self.pubkey_hex))
        wrong[0] ^= 0xFF
        r = self._call("verify_package",
                       {"path": self.pkg, "pubkey_hex": bytes(wrong).hex()})
        self.assertEqual(r["result"], "FAIL")
        s6 = [c for c in r["checks"] if c["id"] == "S6"]
        self.assertTrue(s6 and s6[0]["result"] == "FAIL")


if __name__ == "__main__":
    unittest.main()
