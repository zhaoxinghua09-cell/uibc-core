# Wiring `uibc-mcp` into an MCP client (stdio)

`uibc-mcp` is a **read-only** MCP server. It exposes verification and inspection only;
every write (init / register / event / evidence / submit) stays in the CLI, so an agent
can never mutate evidence through this path.

## Tools (7)

| tool | what it answers |
|---|---|
| `verify_package` | does this package verify, and at which assurance level (integrity / public-key / pinned) |
| `gate_check` | would a governed decision ALLOW / DENY / HOLD for this package |
| `inspect_package` | human-readable summary: agent, owner, evidence count, chain position |
| `cert_verify` | does this certificate match a verified package |
| `get_identity` | which key signed this package, and its `key_id` |
| `list_events` | the lifecycle events in order |
| `list_evidence` | evidence entries with recorded hashes |

## Claude Desktop / Claude Code

```json
{
  "mcpServers": {
    "uibc": {
      "command": "uibc-mcp",
      "args": []
    }
  }
}
```

If `uibc-mcp` is not on PATH (source checkout), point at the module instead:

```json
{
  "mcpServers": {
    "uibc": {
      "command": "python",
      "args": ["-m", "uibc_core.mcp_server"],
      "env": { "PYTHONPATH": "/path/to/uibc-core" }
    }
  }
}
```

## LangChain (Python)

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "uibc": {"command": "uibc-mcp", "args": [], "transport": "stdio"},
})
tools = await client.get_tools()          # the 7 tools above
```

## What this is not

* Not a hosted endpoint. There is no `https://…/mcp` for uibc-core; the server is a local
  process. A hosted endpoint is a distribution choice we have not made.
* Not a writer. If a tool could seal a package, a compromised agent could seal its own
  tampering — read-only is a deliberate boundary, see `docs/api-scope.md`.
* Not a substitute for the CLI. Verification is the same code path; the CLI just has the
  write side.

## 60-second check

```bash
python -m uibc_core.cli demo      # build → seal → stranger verifies → tamper → caught
uibc-mcp                          # then list tools from your client
```
