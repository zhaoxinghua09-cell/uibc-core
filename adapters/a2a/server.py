"""uibc-core A2A Adapter (PROPOSAL) - expose UIBC verification to Agent2Agent
(A2A-style) clients over JSON-RPC 2.0 / HTTP.

Zero dependencies (stdlib only). Read-only surface per docs/api-scope.md v1.0:
the adapter verifies packages that exist on the *server operator's* disk
(operator-trusted model) and returns verification verdicts; it never writes.

JSON-RPC methods (POST /a2a/):
  "card"          -> the agent-card.json content
  "uibc/verify"   -> params {package, key?|did?} -> verify report (S1-S6)
  "uibc/gate"     -> params {package, key?|did?} -> gate decision (ALLOW/DENY/HOLD)
  "uibc/inspect"  -> params {package}            -> human-readable summary fields

Discovery (GET):
  /agent-card.json, /.well-known/agent-card.json, /a2a/card -> the card, with
      `url` rewritten to whatever host the caller used, so the same card is
      correct behind a tunnel, a reverse proxy or a LAN address.
  /.well-known/did.json -> the operator's DID document, when started with
      --did or --did-doc (this is what makes did:web resolvable for us).
  /healthz -> {"status":"ok"} and nothing else: reachability checks should
      not be able to lie about verification capability.

Note: {package} is a path relative to the operator's --packages root; ".."
traversal is rejected.

Run:
  python adapters/a2a/server.py --packages ./examples --port 8899 --host 0.0.0.0
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
from uibc_core import did as did_mod  # noqa: E402

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

    def __init__(self, packages_root, card_path, did_document=None):
        self.packages_root = os.path.abspath(packages_root)
        with open(card_path, "r", encoding="utf-8") as f:
            self.card = json.load(f)
        # Published DID document (optional). Serving it from /.well-known/ is
        # what turns our did:web from a string into something resolvable.
        self.did_document = did_document

    def card_for(self, base_url):
        """Card with `url` rewritten to the host the caller actually used.

        A card that hard-codes 127.0.0.1 is wrong the moment the operator
        tunnels or proxies it, and a wrong service URL in a card is exactly
        how "integrated but unreachable" happens.
        """
        card = dict(self.card)
        card["url"] = base_url + "a2a/"
        interfaces = []
        for item in self.card.get("supportedInterfaces") or []:
            item = dict(item)
            item["url"] = base_url + "a2a/"
            interfaces.append(item)
        if interfaces:
            card["supportedInterfaces"] = interfaces
        return card

    def dispatch(self, method, params):
        if method == "card":
            return self.card
        pkg = _resolve_package(self.packages_root,
                               (params or {}).get("package"))
        key = (params or {}).get("key")  # hex string, same format as .key files
        if key is not None:
            key = bytes.fromhex(key)
        # A caller may pin the key by DID instead of shipping the key itself.
        # That is the difference between "my verifier says PASS" and "any
        # verifier with the DID says PASS".
        pubkey = None
        did_value = (params or {}).get("did")
        if did_value:
            try:
                pubkey, _kid = did_mod.resolve_ed25519_key(did_value)
            except Exception as exc:
                raise ValueError("cannot resolve %s: %s" % (did_value, exc))
        if method == "uibc/verify":
            return verify(pkg, key=key, pubkey=pubkey)
        if method == "uibc/gate":
            report = gate(pkg, key=key, pubkey=pubkey)
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

        def _base_url(self):
            host = self.headers.get("Host")
            if not host:
                host = "127.0.0.1:%d" % self.server.server_port
            # Behind a tunnel or reverse proxy the Host header is right but
            # the scheme is not knowable from the socket, so honour the
            # de-facto X-Forwarded-Proto when it is present.
            scheme = (self.headers.get("X-Forwarded-Proto") or "http").split(",")[0].strip()
            return "%s://%s/" % (scheme or "http", host)

        def do_GET(self):
            path = (self.path or "/").split("?", 1)[0].rstrip("/") or "/"
            if path == "/healthz":
                return self._send_json(200, {"status": "ok"})
            if path in ("/agent-card.json", "/.well-known/agent-card.json",
                        "/a2a/card", "/uibc-a2a/agent-card.json"):
                return self._send_json(200, adapter.card_for(self._base_url()))
            if path == "/.well-known/did.json":
                if adapter.did_document is None:
                    return self._send_json(404, {
                        "error": "no DID document configured",
                        "hint": "start the adapter with --did or --did-doc",
                    })
                return self._send_json(200, adapter.did_document)
            return self._send_json(404, {"error": "not found", "path": path})

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
    # Default stays loopback: binding 0.0.0.0 is a decision about who may poke
    # at this box, so it has to be typed on purpose.
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind address (use 0.0.0.0 only where the operator intends "
                         "external reachability)")
    ap.add_argument("--did", default=None,
                    help="publish the DID document for this DID at /.well-known/did.json "
                         "(did:key or did:web)")
    ap.add_argument("--did-doc", default=None,
                    help="publish a DID document read from this JSON file")
    args = ap.parse_args(argv)

    did_document = None
    if args.did_doc:
        with open(args.did_doc, "r", encoding="utf-8") as f:
            did_document = json.load(f)
    elif args.did:
        try:
            did_document = did_mod.resolve(args.did)
        except Exception as exc:
            ap.error("cannot build the DID document for %s: %s" % (args.did, exc))

    adapter = A2AAdapter(args.packages, args.card, did_document=did_document)
    srv = ThreadingHTTPServer((args.host, args.port), make_handler(adapter))
    print("uibc-core A2A adapter on http://%s:%d (methods: %s)"
          % (args.host, args.port, ", ".join(_METHODS)))
    print("  discovery: GET /agent-card.json  GET /.well-known/did.json  GET /healthz")
    srv.serve_forever()


if __name__ == "__main__":
    main()
