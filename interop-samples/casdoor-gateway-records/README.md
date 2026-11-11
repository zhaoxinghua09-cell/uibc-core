# Interop sample: an MCP gateway's audit records, sealed (Casdoor-style × uibc-core)

**What this is.** A worked example of composability between an
*authorization layer* and an *evidence layer*. A fictional operator runs
an MCP gateway in the style of Casdoor (registration, consent, scopes,
audience binding, per-tool allow/block policy). The gateway's audit
Records for one agent session are exported, and the operator seals the
export as a uibc-core evidence package. An auditor who trusts neither
the operator nor the gateway can then verify the export in one command —
and catch a record that was washed after the fact.

**What this is not.** It is not an official Casdoor integration, not
endorsed by the Casdoor project, and it uses fictional data throughout.
Field names in `records-export.json` follow the audit Record shape
documented for such gateways (timestamp, organization, owner, method,
request URI, action, request body with secrets masked, response);
whether any specific product version emits exactly this shape is for
its own documentation to say.

## The story in the pack

One session, five records. An agent client, delegated by a human
principal (authorization code + PKCE, audience bound to one gateway
server, three scopes granted on consent), calls three tools and is
**blocked** from a fourth (`delete_record` — blocked by the gateway's
tool allow/block list, call not forwarded). The gateway did its job:
Actor identified, Authority enforced. Its records are the Effect.

The gap this sample closes: gateway audit records normally live in the
operator's own database — complete, and completely unverifiable by
anyone else. Sealing the export changes who can check it.

## Five verification runs (RUN-TRANSCRIPT.txt, reproduced by build_demo.py)

| # | Package | Mode | Verdict |
|---|---|---|---|
| 1 | sealed export | open | **PASS** |
| 2 | sealed export | auditor pins operator's public key | **PASS** |
| 3 | washed export — the blocked record rewritten as "ok" after sealing | open | **FAIL** — S4 names `files/records-export.json` |
| 4 | washed export re-sealed with a substitute key | open | **PASS** (honest boundary: unpinned verification proves integrity, not origin) |
| 5 | same re-sealed export | key pinned | **FAIL** — S6 key mismatch |

## IBEA three-field mapping

| Field | The gateway (authorization layer) | The seal (evidence layer) |
|---|---|---|
| **Actor** | Registered client + human principal recorded per call (`owner` field) | The export's contents are frozen at seal time; later edits are detectable |
| **Authority** | DCR/CIMD registration, consent, scope subset, RFC 8707 audience binding, per-tool policy | The recorded delegation context (`gateway-config-summary.json`) is sealed with the records it governed |
| **Effect** | Audit Records in the operator's database — mutable, unsigned, operator-trusted | The same records as a sealed package — third-party verifiable, tamper-evident, verdict PASS / FAIL / INCONCLUSIVE |

## Honest limits

- PASS means: this export is byte-identical to the export the operator
  sealed. It does not prove the gateway recorded everything (a record
  never written cannot be caught by sealing the export), nor that the
  recorded calls were wise.
- The demo keys are published seeds (`operator.key` seed bytes are in
  build_demo.py) so anyone can rebuild the exact packages. Never use a
  published seed for anything real.
- Timestamps in the package are not independently anchored (a stated
  uibc-core limitation).

## Run it

```
git clone https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core
python3 -m uibc_core.cli verify <path-to-this-demo>/packages/exported-sealed
```

Rebuild everything: `python3 build_demo.py` (needs the uibc-core
checkout at /tmp/uibc-main, or edit UIBC_ROOT).

Plain-language verification guide: README-VERIFY.md.
