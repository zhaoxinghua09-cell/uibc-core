"""UIBC Core MCP server (PROPOSAL, read-only).

Exposes the five API categories from docs/api-scope.md as MCP tools,
READ-ONLY per the api-scope decision v1.0: verification and inspection
travel to the caller; all writes stay local (the caller uses the CLI).

Transport: newline-delimited JSON-RPC 2.0 over stdio (MCP stdio spec).
Zero third-party dependencies - MCP protocol surface only.

Run from the repository root:
    python -m mcp_server.server
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.verify import verify            # noqa: E402
from uibc_core.gate import gate                # noqa: E402
from uibc_core.certificate import verify_certificate  # noqa: E402
from uibc_core import __version__              # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "uibc-core", "version": __version__}


def _load_key_hex(key_hex):
    return bytes.fromhex(key_hex) if key_hex else None


def _pkg_report(fn, path, **kw):
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return {"error": f"package directory not found: {path}"}
    return fn(path, **kw)


def _read_json(path, rel):
    p = os.path.join(os.path.abspath(path), rel)
    if not os.path.isfile(p):
        return {"error": f"file not found in package: {rel}"}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- tools

def tool_verify_package(args):
    """S1-S6 verification of a sealed package (open or strict mode)."""
    key = _load_key_hex(args.get("key_hex"))
    return _pkg_report(verify, args.get("path"), key=key)


def tool_gate_check(args):
    """Governed decision ALLOW/DENY/HOLD from verify + revocation/dispute."""
    key = _load_key_hex(args.get("key_hex"))
    rev = args.get("revocation_path")
    disp = args.get("dispute_path")

    def _gate(path):
        return gate(path, key=key,
                    revocation_path=rev, dispute_path=disp)
    return _pkg_report(_gate, args.get("path"))


def tool_inspect_package(args):
    """Human-readable summary: agent, status, events, evidence count, root."""
    path = args.get("path")
    manifest = _read_json(path, "manifest.json")
    if "error" in manifest:
        return manifest
    identity = _read_json(path, "identity.json")
    lifecycle = _read_json(path, "lifecycle.json")
    idx = _read_json(path, os.path.join("evidence", "index.json"))
    return {
        "agent_id": identity.get("agent_id"),
        "owner": identity.get("owner"),
        "status": identity.get("status"),
        "manifest_status": manifest.get("status"),
        "events": [e.get("event_type") for e in lifecycle.get("events", [])],
        "evidence_count": len(idx.get("entries", [])),
        "evidence_root": manifest.get("evidence_root"),
    }


def tool_cert_verify(args):
    """Verify a certificate (C1-C7); optionally bind-check against a package."""
    key = _load_key_hex(args.get("key_hex"))
    if key is None:
        return {"error": "key_hex is required for certificate verification"}
    cert_path = os.path.abspath(args.get("cert_path"))
    if not os.path.isfile(cert_path):
        return {"error": f"certificate file not found: {cert_path}"}
    with open(cert_path, "r", encoding="utf-8") as f:
        cert = json.load(f)
    pkg = args.get("package_dir")
    return verify_certificate(key, cert,
                              package_dir=os.path.abspath(pkg) if pkg else None)


def tool_get_identity(args):
    """Read-only access to a package identity (API category IDENTITY)."""
    return _read_json(args.get("path"), "identity.json")


def tool_list_events(args):
    """Read-only lifecycle event chain (API category LIFECYCLE)."""
    lc = _read_json(args.get("path"), "lifecycle.json")
    if "error" in lc:
        return lc
    return {"events": lc.get("events", [])}


def tool_list_evidence(args):
    """Read-only evidence index with hashes (API category EVIDENCE)."""
    return _read_json(args.get("path"), os.path.join("evidence", "index.json"))


TOOLS = [
    {
        "name": "verify_package",
        "description": ("Verify a sealed .uibc package: S1-S6. Pass key_hex for "
                        "strict mode (unsigned/forged/substituted seals FAIL at S6); "
                        "omit for open mode. Read-only. Exit semantics: result PASS/FAIL."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "package directory"},
                "key_hex": {"type": "string", "description": "owner seal key, 64-char hex (optional, enables strict mode)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "gate_check",
        "description": ("Governed decision: ALLOW/DENY/HOLD (mirrors CLI gate, "
                        "exit 0/2/3). Honors signed revocation; disputes annotate only."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "key_hex": {"type": "string"},
                "revocation_path": {"type": "string"},
                "dispute_path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "inspect_package",
        "description": "Human-readable package summary (agent, status, events, evidence, root).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "cert_verify",
        "description": "Verify an UIBC certificate (C1-C7); optional package binding check.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cert_path": {"type": "string"},
                "key_hex": {"type": "string"},
                "package_dir": {"type": "string"},
            },
            "required": ["cert_path", "key_hex"],
        },
    },
    {
        "name": "get_identity",
        "description": "Read a package identity.json (API category IDENTITY, read-only).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_events",
        "description": "Read a package lifecycle event chain (API category LIFECYCLE, read-only).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_evidence",
        "description": "Read a package evidence index with content hashes (API category EVIDENCE, read-only).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
]

TOOL_FUNCS = {
    "verify_package": tool_verify_package,
    "gate_check": tool_gate_check,
    "inspect_package": tool_inspect_package,
    "cert_verify": tool_cert_verify,
    "get_identity": tool_get_identity,
    "list_events": tool_list_events,
    "list_evidence": tool_list_evidence,
}


# ---------------------------------------------------------------- rpc

def handle(msg):
    """Handle one JSON-RPC message dict, return a response dict or None."""
    method = msg.get("method", "")
    msg_id = msg.get("id")
    if method.startswith("notifications/"):
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name")
        fn = TOOL_FUNCS.get(name)
        if fn is None:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32602,
                              "message": f"unknown tool: {name}"}}
        try:
            result = fn(params.get("arguments", {}))
            return {"jsonrpc": "2.0", "id": msg_id,
                    "result": {"content": [
                        {"type": "text",
                         "text": json.dumps(result, ensure_ascii=False, indent=2)}]}}
        except Exception as exc:  # pragma: no cover - defensive
            return {"jsonrpc": "2.0", "id": msg_id,
                    "result": {"content": [{"type": "text",
                                            "text": f"error: {exc}"}],
                               "isError": True}}
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": -32601, "message": f"method not found: {method}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
