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

## Gateway mode: registration metadata + lifecycle (T/ISC 0174)

Run with `--registry` and the adapter stops being a bare verifier endpoint and
starts behaving like the gateway T/ISC 0174-2026 describes:

```
python adapters/a2a/server.py --packages ./examples --port 8899 \
    --registry registry.json --lifecycle-state lifecycle.json
```

- `registry.json` is validated at startup (0174 6.1.1 a/b); the process refuses
  to start on a half-valid registry instead of forwarding on one. Required
  fields: `name`, `id` (DID), `capabilities`, `protocols`, `endpoint`,
  `organization`; optional but checked when present: `vc`, `authorization`,
  `state`.
- every `uibc/*` call must then name `params.agent`, and that agent must be
  `enabled` **at the moment of the call**. Suspend is enforced per request with
  HTTP 403 / `-32001` and `data.clause = "6.1.3b"` - not by hiding the agent from
  a list, and not only after a restart.
- `resume` re-runs the binding checks (credential status and expiry, organization
  identifier, authorization scopes) and refuses unless all of them are a positive
  yes. A flag flip is not a resumption.
- states persist to `--lifecycle-state`, so a suspend survives a restart.

Extra surfaces in this mode:

| Surface | Clause | What it does |
| --- | --- | --- |
| `gateway/registry` (RPC) | 6.1.1 | validation report, errors and warnings included |
| `gateway/state` (RPC) | 6.1.3 | state snapshot + audit count |
| `gateway/discover` / `GET /agents?q=` | 6.2.1, 6.2.2 a | lookup, enabled-only, ranking basis and score returned |
| `GET /agent-record.json` | 7.2.1 b | Agent Card + registration merged into one record |
| `X-AUIB-Trace-Id` & co. | 7.3.1 d, 9.1.2 a/d | inherited from upstream, generated when absent, echoed back |

Clause-by-clause status, gaps included: `docs/CROSSWALK-ISC-0174.md`, regenerated
by `tools/gateway_conformance.py` (18 live probes, loopback, no mocks).

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
