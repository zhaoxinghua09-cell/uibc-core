"""Build the Casdoor x uibc interoperability sample packages.

Story (fictional session, real formats): an operator runs an MCP gateway
whose authorization decisions are recorded as audit Records. The Records
for one agent session are exported; the operator seals the export as a
uibc evidence package; an independent auditor verifies it with one
command - and catches a washed record.

Field names in records-export.json follow the Record shape documented
for Casdoor (timestamp, organization, user, method, request URI, action,
request body with secrets masked, response). All names, organisations
and calls are fictional. This is NOT an official Casdoor integration;
it demonstrates composability: an authorization layer's records become
third-party-verifiable evidence once sealed.

Demo keys use published seeds on purpose. DEMO ONLY.
Run:  python3 build_demo.py   (uibc-core checkout at /tmp/uibc-main)
"""
import json
import os
import shutil
import subprocess
import sys

UIBC_ROOT = "/tmp/uibc-main"
sys.path.insert(0, UIBC_ROOT)

import uibc_core.cli as ucli  # noqa: E402
from uibc_core.signing import ed_public_key  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PKGS = os.path.join(HERE, "packages")
SRC = os.path.join(HERE, "_src")

OPERATOR_SEED = bytes([11] * 32)  # DEMO ONLY - published, by design
ATTACKER_SEED = bytes([13] * 32)  # DEMO ONLY - substitute-key signer

URI = "/api/server/acme-health/device-registry-mcp"
BLOCKED = "error: blocked by tool allow/block list (JSON-RPC error returned, call not forwarded)"

def rec(ts, action, body, response):
    return {
        "createdTime": ts,
        "organization": "acme-health",
        "owner": "app/clinical-support-agent (on behalf of user j.osei)",
        "clientIp": "10.4.1.27",
        "method": "POST",
        "requestUri": URI,
        "action": action,
        "requestBody": body,
        "response": response,
    }

RECORDS = [
    rec("2026-11-10T09:14:02Z", "mcp-tools-list",
        '{"jsonrpc":"2.0","id":1,"method":"tools/list"}', "ok"),
    rec("2026-11-10T09:14:19Z", "mcp-tools-call",
        '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"query_device_registry","arguments":{"udi":"(01)06912345678901"},"authorization":"***"}}',
        "ok"),
    rec("2026-11-10T09:15:44Z", "mcp-tools-call",
        '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"read_document","arguments":{"doc":"ifu-cp2-rev-c"}}}',
        "ok"),
    rec("2026-11-10T09:17:03Z", "mcp-tools-call",
        '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"update_ticket","arguments":{"ticket":"INC-2211","note":"registry entry confirmed"}}}',
        "ok"),
    rec("2026-11-10T09:18:37Z", "mcp-tools-call",
        '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"delete_record","arguments":{"record":"reg-88412"}}}',
        BLOCKED),
]

EXPORT = {
    "export_note": "FICTIONAL session. Field names follow the audit Record shape documented for Casdoor-style gateways: createdTime, organization, owner, clientIp, method, requestUri, action, requestBody (secrets masked), response.",
    "exported_from": "MCP gateway audit records (operator console export)",
    "exported_by": "acme-health-ops",
    "exported_at": "2026-11-10T10:02:00Z",
    "server": "acme-health/device-registry-mcp",
    "records": RECORDS,
}

CONFIG = {
    "gateway_server": "acme-health/device-registry-mcp",
    "upstream": "device-registry MCP server (operator-run)",
    "client_registration": "dynamic client registration (DCR), client tagged dcr",
    "delegation": {
        "human_principal": "j.osei (clinical engineering)",
        "agent_client": "clinical-support-agent",
        "flow": "authorization code + PKCE (S256), RFC 8707 resource indicator",
        "audience": URI,
        "scopes_granted": ["device-registry:read", "documents:read", "tickets:write"],
        "consent": "recorded on the operator's consent page; subset of requested scopes",
        "token_lifetimes": "access 168h / refresh 720h (gateway defaults), refresh rotation on",
    },
    "tool_policy": {
        "query_device_registry": "allow",
        "read_document": "allow",
        "update_ticket": "allow",
        "delete_record": "block",
    },
}

SUMMARY = """SESSION SUMMARY - fictional MCP gateway session (Casdoor-style gateway)
An agent client, delegated by a human principal, called three tools
through the gateway and was blocked from a fourth. The gateway did the
authorization: registration, consent, scopes, audience binding, per-tool
policy. Its audit records say what happened.

What the gateway does not do: make those records provable to anyone
else. The records live in the operator's database, editable by the
operator. This package seals one export of them, so an auditor who
trusts neither the operator nor the gateway can still check that the
export they hold is the export that was sealed - and catch a record
that was washed after the fact.
"""

EDITED_RESPONSE = "ok"


def _a(**kw):
    return type("A", (), kw)()


def write_key(seed, key_path, pub_path=None):
    with open(key_path, "w", encoding="ascii") as f:
        f.write("ed25519:" + seed.hex())
    if pub_path:
        with open(pub_path, "w", encoding="ascii") as f:
            f.write(ed_public_key(seed).hex())


def records_text(edited):
    data = json.loads(json.dumps(EXPORT))
    if edited:
        data["records"][4]["response"] = EDITED_RESPONSE
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def build_package(dest, edited, key_path):
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(SRC, exist_ok=True)
    files = {
        "records-export.json": (records_text(edited), "ACTION", "application/json",
                                "gateway audit records export for one agent session"),
        "gateway-config-summary.json": (json.dumps(CONFIG, indent=2) + "\n", "INPUT",
                                        "application/json",
                                        "authorization context recorded by the gateway operator"),
        "session-summary.txt": (SUMMARY, "OUTPUT", "text/plain",
                                "plain-language session summary"),
    }
    paths = {}
    for name, (text, _t, _m, _n) in files.items():
        p = os.path.join(SRC, name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        paths[name] = p
    ucli.cmd_init(_a(path=dest))
    ucli.cmd_register(_a(path=dest, agent_id="casdoor-gateway-session-export",
                         owner="acme-health-ops",
                         agent_type="evidence-package", version="1.0.0"))
    ucli.cmd_event(_a(path=dest, type="ACTIVATE", actor="acme-health-ops"))
    for name, p in paths.items():
        _text, etype, media, note = files[name]
        ucli.cmd_evidence(_a(path=dest, type=etype, file=p,
                             media_type=media, note=note))
    ucli.cmd_submit(_a(path=dest, key=key_path))


def run_verify(args):
    cmd = [sys.executable, "-m", "uibc_core.cli", "verify"] + args
    env = dict(os.environ, PYTHONPATH=UIBC_ROOT)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=UIBC_ROOT)
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    if os.path.isdir(PKGS):
        shutil.rmtree(PKGS)
    os.makedirs(PKGS)
    op_key = os.path.join(HERE, "operator.key")
    op_pub = os.path.join(HERE, "operator.pub")
    atk_key = os.path.join(HERE, "attacker.key")
    write_key(OPERATOR_SEED, op_key, op_pub)
    write_key(ATTACKER_SEED, atk_key)

    sealed = os.path.join(PKGS, "exported-sealed")
    build_package(sealed, edited=False, key_path=op_key)

    edited = os.path.join(PKGS, "exported-edited")
    shutil.copytree(sealed, edited)
    target = os.path.join(edited, "evidence", "files", "records-export.json")
    text = open(target, encoding="utf-8").read()
    assert text.count(BLOCKED) == 1
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        f.write(text.replace(BLOCKED, EDITED_RESPONSE))

    resealed = os.path.join(PKGS, "exported-resealed")
    build_package(resealed, edited=True, key_path=atk_key)

    lines = []
    lines.append("CASDOOR x UIBC INTEROP SAMPLE - verification transcript")
    lines.append("Story: one fictional agent session through an MCP gateway.")
    lines.append("The gateway blocked a delete_record call. Its audit export")
    lines.append("was sealed. In the washed variant, the blocked record was")
    lines.append("rewritten to look like a success.")
    lines.append("=" * 62)
    cases = [
        ("1. Sealed export, open verification", [sealed]),
        ("2. Sealed export, auditor pins the operator public key",
         ["--pubkey", op_pub, sealed]),
        ("3. Washed export (blocked record rewritten as ok)", [edited]),
        ("4. Washed export re-sealed with a substitute key, open verification",
         [resealed]),
        ("5. Same re-sealed export, auditor pins the operator public key",
         ["--pubkey", op_pub, resealed]),
    ]
    for title, args in cases:
        code, out = run_verify(args)
        lines.append("")
        lines.append(title)
        lines.append(f"  $ uibc verify {' '.join(args).replace(PKGS + '/', '')}")
        for ln in out.splitlines():
            lines.append("  " + ln)
        lines.append(f"  exit code: {code}")
    transcript = "\n".join(lines) + "\n"
    with open(os.path.join(HERE, "RUN-TRANSCRIPT.txt"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(transcript)
    print(transcript)


if __name__ == "__main__":
    main()
