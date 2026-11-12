# UIBC Core MCP Server (read-only)

Exposes UIBC verification as MCP tools so any MCP-capable AI client can
verify packages without installing anything beyond this repo.

Scope (per docs/api-scope.md decision v1.0): **read-only**. Verification,
gate decisions, certificates, and package reads are exposed; all writes
(init/register/evidence/submit/keygen) remain CLI-local — a public write
surface would be a key-management hazard. Since v0.3, `verify_package`
and `gate_check` also accept `pubkey_hex` to pin the expected Ed25519
signer (a substituted key FAILS S6).

## Run

Installed from PyPI (zero dependencies):

```
pip install uibc-core
uibc-mcp
```

From a source checkout:

```
python -m uibc_core.mcp_server
```

(Legacy path `python -m mcp_server.server` still works via a shim.)

Register in an MCP client (example config):

```json
{
  "mcpServers": {
    "uibc-core": {
      "command": "python",
      "args": ["-m", "uibc_core.mcp_server"],
      "cwd": "/path/to/uibc-core"
    }
  }
}
```

## Tools (7, all read-only)

| Tool | API category | Purpose |
|---|---|---|
| verify_package | VERIFY | S1-S6 verification (open/strict) |
| gate_check | GATE | ALLOW/DENY/HOLD decision |
| inspect_package | — | human-readable summary |
| cert_verify | VERIFY | certificate C1-C7 checks |
| get_identity | IDENTITY | read identity.json |
| list_events | LIFECYCLE | read event chain |
| list_evidence | EVIDENCE | read evidence index + hashes |

Honest limits: the server trusts the local filesystem it reads from; it
does not authenticate callers (single-user local deployment assumption);
no remote transport is provided.
