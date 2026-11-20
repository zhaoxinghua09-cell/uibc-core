# A2A Adapter (v0.3 - HTTP server, operator-trusted, DID-addressable)

Goal: let agents speaking the A2A (Agent2Agent) protocol discover and
invoke UIBC verification as an agent skill - "verify this package" becomes
an A2A message exchange instead of a CLI call.

## Status: JSON-RPC 2.0 over HTTP, runnable, discoverable

`server.py` is a zero-dependency JSON-RPC 2.0 adapter:

```
python adapters/a2a/server.py --packages ./examples --port 8899 --host 0.0.0.0 \
    --did did:web:medxpert.cn
```

JSON-RPC methods (see `MAPPING.md` for the A2A <-> UIBC translation):
- `card`         - returns `agent-card.json`
- `uibc/verify`  - `{package, key?|did?}` -> full S1-S6 verify report
- `uibc/gate`    - `{package, key?|did?}` -> gate decision + report
- `uibc/inspect` - `{package}` -> identity summary

Discovery endpoints (GET):
- `/agent-card.json`, `/.well-known/agent-card.json`, `/a2a/card` - the card,
  with `url` rewritten from the request's Host (and `X-Forwarded-Proto`), so
  the same card stays correct behind a tunnel, a proxy or a LAN address.
- `/.well-known/did.json` - the operator's DID document, when started with
  `--did` or `--did-doc`. This is what makes a `did:web` identity resolve.
- `/healthz` - `{"status":"ok"}` only. Reachability checks must not be able to
  claim verification capability.

## Verifying with a DID instead of a key

Before v0.3 a caller who wanted a real (non-HMAC) verdict had to be handed the
owner's public key out of band. With `--did`, `did?` or `--did` the verifier
resolves the key **from the DID the package names**:

```
uibc verify ./pkg --did did:key:z6Mk...          # offline, no network
uibc verify ./pkg --did did:web:medxpert.cn      # key fetched over https
```

Supported: `did:key` (offline) and `did:web` (https). Deliberately **not**
supported: `did:cn:agent`, `did:ioa`, `did:wba` - no published resolution rule
exists for them as of 2026-11-20, and inventing one would produce a resolver
that looks authoritative and is wrong. Binding an identity to a DID nobody
else can resolve proves nothing about who controls it, so `register --did`
refuses those methods at write time rather than failing mysteriously later.

## Trust model (**operator-trusted**, read-only)

The adapter verifies packages that exist under the operator's `--packages`
root on the operator's disk. It never writes; path traversal is rejected.
This is consistent with docs/api-scope.md (reads may be public, writes stay
local with the owner). It is NOT yet an interoperability-tested A2A
reference client implementation - that remains the post-Ed25519 milestone.

## Why an adapter and not a fork

A2A and UIBC solve different layers: A2A is transport/discovery between
agents; UIBC is evidence/verification about what agents did. The adapter
keeps both clean (Storage ≠ Protocol, the same discipline as
docs/api-scope.md): A2A carries the request, UIBC does the judging.
