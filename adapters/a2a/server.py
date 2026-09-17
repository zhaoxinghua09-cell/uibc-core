"""uibc-core A2A Adapter (PROPOSAL) - expose UIBC verification to Agent2Agent
(A2A-style) clients over JSON-RPC 2.0 / HTTP.

Zero dependencies (stdlib only). Read-only surface per docs/api-scope.md v1.0:
the adapter verifies packages that exist on the *server operator's* disk
(operator-trusted model) and returns verification verdicts; it never writes.

JSON-RPC methods:
  "card"          -> the agent-card.json content
  "uibc/verify"   -> params {package, key?}  -> verify report (S1-S6)
  "uibc/gate"     -> params {package, key?}  -> gate decision (ALLOW/DENY/HOLD)
  "uibc/inspect"  -> params {package}        -> human-readable summary fields

Note: {package} is a path relative to the operator's --packages root; ".."
traversal is rejected.

Run:
  python adapters/a2a/server.py --packages ./examples --port 8899
"""

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core.verify import verify  # noqa: E402
from uibc_core.gate import gate  # noqa: E402

JSONRPC_VERSION = "2.0"
_METHODS = ("card", "uibc/verify", "uibc/gate", "uibc/inspect")


def _resolve_package(packages_root, rel):
    if not isinstance(rel, str) or not rel:
        raise ValueError("params.package must be a non-empty relative path")
    norm = os.path.normpath(rel)
    if os.path.isabs(norm) or norm.startswith(".."):
        raise ValueError("path traversal rejected")
    pkg = os.path.join(packages_root, norm)
    if not os.path.isdir(pkg):
        raise FileNotFoundError("package not found: %s" % rel)
    return pkg


class A2AAdapter:
    """Method dispatch, separated from HTTP so tests can call it directly."""

    def __init__(self, packages_root, card_path):
        self.packages_root = os.path.abspath(packages_root)
        with open(card_path, "r", encoding="utf-8") as f:
            self.card = json.load(f)

    def dispatch(self, method, params):
        if method == "card":
            return self.card
        pkg = _resolve_package(self.packages_root,
                               (params or {}).get("package"))
        key = (params or {}).get("key")  # hex string, same format as .key files
        if key is not None:
            key = bytes.fromhex(key)
        if method == "uibc/verify":
            return verify(pkg, key=key)
        if method == "uibc/gate":
            report = gate(pkg, key=key)
            return {"decision": report.get("decision"),
                    "reason": report.get("reason",
                                         report.get("detail", "")),
                    "report": report}
        if method == "uibc/inspect":
            with open(os.path.join(pkg, "identity.json"), "r",
                      encoding="utf-8") as f:
                identity = json.load(f)
            return {"identity": identity.get("agent_id", identity.get("id")),
                    "spec_version": identity.get("spec_version")}
        raise ValueError("unknown method: %s" % method)


def make_handler(adapter):
    class A2AHandler(BaseHTTPRequestHandler):
        def _send_json(self, code, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _rpc_error(self, rid, code, message):
            self._send_json(200, {"jsonrpc": JSONRPC_VERSION, "id": rid,
                                  "error": {"code": code, "message": message}})

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                return self._rpc_error(None, -32700, "parse error")
            rid = req.get("id")
            method = req.get("method")
            if req.get("jsonrpc") != JSONRPC_VERSION:
                return self._rpc_error(rid, -32600, "invalid request: jsonrpc must be '2.0'")
            if method not in _METHODS:
                return self._rpc_error(rid, -32601, "method not found: %s" % method)
            try:
                result = adapter.dispatch(method, req.get("params"))
            except (ValueError, FileNotFoundError) as exc:
                return self._rpc_error(rid, -32602, "invalid params: %s" % exc)
            except Exception as exc:  # verify failures etc. are results, not errors
                return self._rpc_error(rid, -32000, "internal error: %s" % exc)
            self._send_json(200, {"jsonrpc": JSONRPC_VERSION, "id": rid,
                                  "result": result})

        def log_message(self, fmt, *args):
            pass

    return A2AHandler


def main(argv=None):
    ap = argparse.ArgumentParser(description="uibc-core A2A adapter (JSON-RPC 2.0 over HTTP)")
    ap.add_argument("--packages", required=True, help="root dir of verifiable packages")
    ap.add_argument("--card", default=os.path.join(os.path.dirname(__file__), "agent-card.json"))
    ap.add_argument("--port", type=int, default=8899)
    args = ap.parse_args(argv)
    adapter = A2AAdapter(args.packages, args.card)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(adapter))
    print("uibc-core A2A adapter on http://127.0.0.1:%d (methods: %s)"
          % (args.port, ", ".join(_METHODS)))
    srv.serve_forever()


if __name__ == "__main__":
    main()
