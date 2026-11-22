# XLGD Trust Lifecycle — Independent Reproduction Kit

**Purpose**: let an outside developer verify XLGD trust-lifecycle semantics without importing any XLGD code or installing project dependencies.

**Status**: self-run only. There is **0 external reproduction** as of 2026-11-19. Running this kit does not make you a certifier, and a green result here is not a third-party attestation.

## Requirements

- Python 3.9+ (standard library only)
- No network access needed

## Run

```bash
python run.py --out external_node_result.json
```

Set reporter identity (required for a valid third-party submission):

```bash
REPRODUCER="Jane Doe" AFFILIATION="Example University" CONFLICT_DECLARED="false" \
  python run.py --out external_node_result.json
```

Exit code `0` = all vectors matched your run's expectation table; `1` = at least one mismatch (see `mismatches`).

## What is inside

| File | Content |
|---|---|
| `vectors.json` | 30 language-neutral vectors: inputs + expected verdict (14 lifecycle + 6 passport exchange + 10 canonicalization/negotiation) |
| `run.py` | Reference runner, Python 3.9+ standard library only |
| `run.mjs` | Second implementation in Node.js (zero dependencies) — proves cross-language reachability, **not** independent validation |
| `make_vectors.py` | Regenerates `vectors.json` with HMAC fixtures |
| `RESULT.schema.json` | Shape of the result file you return |
| `external_node_result_selfrun.json` | Python run (self-run, not third-party) |
| `external_node_result_node.json` | Node run (self-run, same author, not third-party) |

## Vectors

| ID | Check | Scenario | Expected |
|---|---|---|---|
| V-01 | binding | valid signature, registered digest | ALLOW |
| V-02 | binding | content changed, re-signed by same key | REJECT |
| V-03 | binding | signer key ≠ key registered for subject | REJECT |
| V-04 | binding | unregistered key id | REJECT |
| V-05 | usable | AUTHORIZED, 20 days left | ALLOW |
| V-06 | usable | AUTHORIZED, expired yesterday | REJECT |
| V-07 | usable | state UNKNOWN | REJECT |
| V-08 | transition | score-only authorization attempt | REJECT |
| V-09 | transition | authorization with subject/scope/expires | ALLOW |
| V-10 | compat | uibc/0.4.0 + rules/2 + engine/3 | ALLOW |
| V-11 | compat | uibc/0.3.x + rules/2 + engine/3 | REJECT |
| V-12 | compat | unregistered version triple | REJECT |
| V-13 | revocation | identity revoked, cascaded to auth | REJECT |
| V-14 | revocation | unrelated subject unaffected | ALLOW |
| V-15 | exchange | full passport, fresh snapshot, in-scope | ALLOW |
| V-16 | exchange | entity revoked in a fresh snapshot | REJECT |
| V-17 | exchange | snapshot 30h old vs max 6h | REJECT |
| V-18 | exchange | no revocation source at all | REJECT |
| V-19 | exchange | another entity revoked, this one not | ALLOW |
| V-20 | exchange | evaluation triple outside compat table | REJECT |

V-15…V-20 implement **GTP/1** (`../specs/GTP-1.md`): a platform C that holds only a pinned fingerprint, a compatibility table and a revocation snapshot must reach the same verdict as the issuer.

| ID | Check | Scenario | Expected |
|---|---|---|---|
| V-21 | canon | duplicate key in raw JSON (`entity` twice) | REJECT |
| V-22 | canon | NFC registered vs NFD presented | ALLOW |
| V-23 | canon | `NaN` literal in payload | REJECT |
| V-24 | canon | integer beyond 2^53 | REJECT |
| V-25 | canon | non-canonical number form (`1.0` vs `1`) | REJECT |
| V-26 | negotiate | peer announces unknown higher version | REJECT |
| V-27 | negotiate | peer version below local evidence version | REJECT |
| V-28 | revmerge | two revocation sources, entity not revoked by either | ALLOW |
| V-29 | revmerge | revoked by one source, clear in the other | REJECT |
| V-30 | skew | snapshot 5 min in the future, tolerance 10 min | ALLOW |

V-21…V-25 are the **canonicalization attack surface**: the same bytes can be parsed into different objects (or different bytes into the same object), which is how signature checks get bypassed in practice. These are the cases most implementations silently get wrong.
V-28/V-29 define multi-source merge (union, no "trust the newest source" shortcut).
V-30 defines clock-skew tolerance — tolerance of a *future* timestamp is not a relaxation of the max-age rule.

## Rule semantics (implement these yourself if you prefer)

1. **Binding**: `mac == HMAC(SHA256, canon(body), key)` AND `key_id` equals the key registered for `body.subject` AND `SHA256(canon(body))` equals `registered_digest`.
2. **Usable**: state ∈ {AUTHORIZED, MONITORED} AND `expires_at` present AND `expires_at > now`.
3. **Transition**: `AUTHORIZED` requires `subject`, `scope`, `expires_at`; a numeric score alone never authorizes.
4. **Compatibility**: only explicitly registered (evidence_version, rule_version, engine) triples pass; unknown = reject.
5. **Revocation**: revoked target or any object in its `propagates_to` is unusable.
6. **Exchange (GTP/1)**: pinned fingerprint must equal identity fingerprint; `(rule_version, engine_version)` must be listed in the local compatibility table; `expires_at > now`; `requested_scope ⊆ granted_scope`; a snapshot must exist, its age must not exceed `max_snapshot_age_hours` (default 6), and the entity must not appear in `snapshot.revoked`. A missing or stale snapshot is a **hard reject**, never a warning.
7. **Canonicalization**: inputs with duplicate object keys, non-standard literals (`NaN`/`Infinity`), integers beyond 2^53, or non-canonical number forms (`1.0`) must be rejected — never "parse and hope". Text must be NFC-normalized before hashing.
8. **Negotiation**: only versions in the local support list may be accepted; an unknown higher version or a lower peer version must be rejected (no silent upgrade, no silent downgrade).
9. **Revocation merge**: when several sources exist, take the **union**; an entity revoked by any source is unusable. "Newest source wins" is wrong.
10. **Clock skew**: a small future offset (within `tolerance_minutes`) is tolerated; it never relaxes `max_age`.

`canon` = JSON with `sort_keys=True`, `ensure_ascii=False`, separators `(",", ":")`, UTF-8.

## Honest limits

- These vectors test **rule semantics**, not the XLGD reference implementation's internals.
- Passing all 30 means your implementation agrees with this specification table — nothing more.
- `run.py` and `run.mjs` were written by the **same author**. Their agreement (30/30 and 0 cross-language diff) proves the vectors are language-neutral, **not** that they are correct, and **not** that they have been independently reproduced. Independent means: someone with no relationship to this project runs the kit on their own machine.
- Independence is established by **who runs it and where**, not by the result. A local run on the maintainer's machine counts as self-evaluation and must be labeled `self`.
