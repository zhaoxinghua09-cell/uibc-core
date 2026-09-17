"""uibc-core Registry Server (PROPOSAL) - read-only HTTP access to the three
append-only registries (certificates / revocations / disputes).

Zero dependencies (stdlib only). Follows docs/api-scope.md v1.0:
this server READS registry JSONL files and serves them; it never writes.
Writes stay local via the owner's CLI / file operations.

Endpoints:
  GET /                     -> service info (JSON)
  GET /registry/<name>      -> JSON array of entries, name in
                               {certificates, revocations, disputes}
  GET /health               -> {"status": "ok"}

Run:
  python registry_server/server.py --registry-dir ../registry --port 8765
"""

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REGISTRY_NAMES = ("certificates", "revocations", "disputes")


def load_registry(registry_dir, name):
    """Read a JSONL registry file; return list of parsed entries.
    Empty/missing file -> empty list (a registry starts empty)."""
    if name not in REGISTRY_NAMES:
        raise ValueError("unknown registry: %s" % name)
    path = os.path.join(registry_dir, name + ".jsonl")
    entries = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    return entries


def make_handler(registry_dir):
    class RegistryHandler(BaseHTTPRequestHandler):
        def _send_json(self, code, payload):
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = self.path.split("?", 1)[0].rstrip("/") or "/"
            if route == "/health":
                self._send_json(200, {"status": "ok"})
            elif route == "/":
                self._send_json(200, {
                    "service": "uibc-core registry server",
                    "read_only": True,
                    "registries": list(REGISTRY_NAMES),
                    "spec": "uibc-core/0.2.1-proposal",
                })
            elif route.startswith("/registry/"):
                name = route[len("/registry/"):]
                if name not in REGISTRY_NAMES:
                    self._send_json(404, {"error": "unknown registry", "got": name})
                    return
                try:
                    entries = load_registry(registry_dir, name)
                except (json.JSONDecodeError, ValueError) as exc:
                    # honesty policy: a corrupt registry entry must never be
                    # silently hidden -- fail loudly so the operator fixes it.
                    self._send_json(500, {"error": "corrupt registry file",
                                          "detail": str(exc)})
                    return
                self._send_json(200, {"registry": name, "entries": entries})
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            # Read-only by design (api-scope v1.0). Explicit refusal, not silence.
            self._send_json(405, {"error": "registry server is read-only; "
                                           "append entries via the owner's local CLI"})

        def log_message(self, fmt, *args):
            pass  # keep stdout clean in tests

    return RegistryHandler


def main(argv=None):
    ap = argparse.ArgumentParser(description="uibc-core read-only registry server")
    ap.add_argument("--registry-dir", required=True,
                    help="directory containing certificates/revocations/disputes .jsonl")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.registry_dir))
    print("uibc-core registry server on http://127.0.0.1:%d (read-only)" % args.port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
