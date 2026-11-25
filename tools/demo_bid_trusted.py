# -*- coding: utf-8 -*-
"""§4.2.4 demo: a real HTTP resolver that lies, and a client that doesn't believe it.

    python tools/demo_bid_trusted.py

Five cases against a local `http.server` (no network, no credentials). The
resolver is addressed as `http://127.0.0.1:<port>/<answer>` and the client appends
`/<did>?verify=true`, which is exactly the §4.2.4 request shape:

  1  honest resolver, signed document             -> trusted / fully trusted
  2  resolver claims verify=true, document tampered -> NOT trusted (we re-check)
  3  resolver says verify=false                   -> not trusted, and no exception
  4  delegateSign, signer key supplied            -> fully trusted
  4b delegateSign, no way to fetch the signer key -> trusted, delegate unchecked

Case 2 is the whole point: a client that stops at `data.verify` prints OK there.
"""
import json
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from uibc_core import bid_protocol as B  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
SIGNED = json.loads((REPO / "fixtures" / "bid" / "signed_document.json").read_text(encoding="utf-8"))
DID = SIGNED["id"]
SIGNER_SEED = bytes([0x11] * 32)
SIGNER_ID = "did:bid:efJgt44mNDewKK1VEN454R17cjso3mSG#key-1"
SIGNER_HEX = "b06566" + B.ed_public_key(SIGNER_SEED).hex()


def envelope(doc, verify, version="1.0.0"):
    return {"errorCode": 0, "message": "success",
            "data": {"version": version, "verify": verify, "didDocument": doc}}


def with_delegate():
    doc = json.loads(json.dumps(SIGNED))
    sig = B.ed_sign(SIGNER_SEED, B.delegate_signing_bytes(doc))
    doc["extension"] = dict(doc["extension"])
    doc["extension"]["delegateSign"] = {"signer": SIGNER_ID, "signatureValue": B.base58_encode(sig)}
    return B.sign_bid_document(doc, bytes(range(32)), SIGNED["authentication"][0])


DOCS = {
    "honest": envelope(SIGNED, True),
    "tampered": envelope(dict(SIGNED, created="2021-06-24T09:10:10Z"), True),
    "unverified": envelope(SIGNED, False),
    "delegated": envelope(with_delegate(), True),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib naming
        parsed = urlparse(self.path)
        answer = parsed.path.strip("/").split("/")[0]
        assert parse_qs(parsed.query).get("verify") == ["true"], "client must send ?verify=true"
        body = DOCS.get(answer) or {"errorCode": 6, "message": "not found"}
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


def main():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    base = "http://127.0.0.1:%d" % server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("local resolver at %s\n" % base)

    cases = [
        ("1  honest, signed", "honest", {}),
        ("2  says verified, doc tampered", "tampered", {}),
        ("3  says NOT verified", "unverified", {}),
        ("4  delegate, signer key supplied", "delegated", {"delegate_key_resolver": lambda kid: SIGNER_HEX}),
        ("4b delegate, no signer key", "delegated", {}),
    ]
    rows = []
    for label, answer, kwargs in cases:
        try:
            r = B.resolve_bid_trusted("%s/%s" % (base, answer), DID, **kwargs)
            rows.append((label, "trusted" if r.trusted else "NOT trusted",
                         "fully" if r.fully_trusted else r.delegate_state, r.reason[:64]))
        except Exception as exc:  # noqa: BLE001
            rows.append((label, "error", "-", "%s: %s" % (type(exc).__name__, exc)[:64]))

    width = max(len(r[0]) for r in rows)
    for label, verdict, state, reason in rows:
        print("%-*s | %-12s | %-9s | %s" % (width, label, verdict, state, reason))
    server.shutdown()
    print("\ncase 2: verify=true is the resolver's claim, not evidence.")


if __name__ == "__main__":
    main()
