# A2A Adapter (PROPOSAL v0.2 - HTTP server, operator-trusted)

Goal: let agents speaking Google's A2A (Agent2Agent) protocol discover and
invoke UIBC verification as an agent skill - "verify this package" becomes
an A2A message exchange instead of a CLI call.

## Status: JSON-RPC 2.0 over HTTP, runnable

`server.py` is a zero-dependency JSON-RPC 2.0 adapter:

```
python adapters/a2a/server.py --packages ./examples --port 8899
```

Methods (see `MAPPING.md` for the A2A <-> UIBC translation):
- `card`         - returns `agent-card.json`
- `uibc/verify`  - `{package, key?}` -> full S1-S6 verify report
- `uibc/gate`    - `{package, key?}` -> gate decision + report
- `uibc/inspect` - `{package}` -> identity summary

Trust model (**operator-trusted**, read-only): the adapter verifies packages
that exist under the operator's `--packages` root on the operator's disk.
It never writes; path traversal is rejected. This is consistent with
docs/api-scope.md (reads may be public, writes stay local with the owner).
It is NOT yet an interoperability-tested A2A reference client
implementation - that remains the post-Ed25519 milestone.

## Why an adapter and not a fork

A2A and UIBC solve different layers: A2A is transport/discovery between
agents; UIBC is evidence/verification about what agents did. The adapter
keeps both clean (Storage ≠ Protocol, the same discipline as
docs/api-scope.md): A2A carries the request, UIBC does the judging.
