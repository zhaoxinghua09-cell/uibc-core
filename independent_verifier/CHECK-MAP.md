# Independent verifier ↔ reference check mapping (V1–V9 ↔ S0–S19)

Purpose: make the second implementation's coverage auditable check by check,
instead of only comparing the top-level verdict. Agreement on a mapped check
is a spec-determinism signal; an unmapped reference check is a coverage gap
in the independent verifier, not a pass.

Independence note: this verifier is code-independent from `uibc_core` (zero
shared imports, written from the spec) but **not organisationally
independent** — same maintainer, same trust root. See `iverify.py` header.

## Legend

- **full** — the independent check answers the same question as the reference.
- **partial** — covers part of the reference check; listed sub-points are not
  evaluated by the independent verifier.
- **missing** — no corresponding independent check exists.

## Mapping

| Ref | Reference check (`uibc_core.verify`) | Independent | Coverage | Independent-verifier gap |
|---|---|---|---|---|
| S0 | verifier robustness (hostile input must not crash) | — | missing | no robustness harness in the second implementation |
| S1 | package structure: required files + undeclared root/evidence files | V1, V7 | partial | V1 checks required files; V7 checks undeclared root files only. Reference also audits uncommitted files under `evidence/`, structural members under `evidence/`, and auxiliary directories. |
| S2 | identity consistency | V2 | partial | V2 compares `agent_id` across identity/manifest. Reference also checks `principal_type` enum, `policy_hash` shape, `key_custody` enum, and `agent_id` derivation from `logical_agent_id`. |
| S3 | lifecycle state machine + v1.1 semantics | V3 | partial | V3 reimplements L1–L7 chain/state rules. Reference also runs the v1.1 semantic strictness layer (`l_strict`). |
| S4 | evidence integrity: content hash, known type, evidence_id | V4 | partial | V4 recomputes file hashes and checks evidence type. Reference also requires `evidence_id` and rejects duplicate ids. |
| S5 | evidence aggregate root | V5 | full | same order-independent root over recomputed content hashes. |
| S6 | seal signature (HMAC owner / Ed25519 public) | V6 | partial | V6 verifies HMAC with owner key and Ed25519 publicly. **No pinned-public-key comparison**: a key-substituted re-seal verifies against the new key and passes V6 unless a pubkey pin is supplied (see P1-4). |
| S7 | evidence index metadata digest | V8 | full | metadata-only digest over path/type/note/action_digest, sorted. |
| S8 | package checkpoint head (manifest vs on-disk state) | V9 | partial | V9 recomputes the checkpoint head from lifecycle/root/index/count. Reference also distinguishes a log that was trimmed after sealing. |
| S9 | head pinned out-of-band (rollback / older-package substitution) | — | missing | no out-of-band observed-head comparison in the independent verifier; an older fully self-consistent package passes. |
| S10 | attestation closure declared | — | missing | attestation-set closure check not implemented. |
| S11 | strict serialization (byte-level: duplicates, raw controls, NaN/Inf) | — | missing | byte-level strict serialization not implemented. |
| S12 | timestamp / identifier strictness (RFC 3339, UUID, whitespace) | — | missing | value-level timestamp/identifier validation not implemented. |
| S13 | Merkle inclusion proofs | — | missing | RFC 6962 inclusion proof verification not implemented. |
| S14 | strict base64 | — | missing | strict base64 decoder/shape check not implemented. |
| S15 | anchor event resolution | — | missing | anchor inclusion/root resolution not implemented. |
| S16 | external timestamp (RFC 3161) | — | missing | TSA token verification not implemented. |
| S17 | linear receipt chain | — | missing | receipt chain verification not implemented. |
| S18 | policy artefact resolution | — | missing | policy digest artefact resolution not implemented. |
| S19 | freshness state (opt-in, first observation INCONCLUSIVE) | — | missing | freshness/head-observation state not implemented. |

## Coverage summary

- full: S5, S7
- partial: S1, S2, S3, S4, S6, S8
- missing: S0, S9, S10, S11, S12, S13, S14, S15, S16, S17, S18, S19

The independent verifier currently exercises the core structure/identity/
lifecycle/integrity/root/seal/checkpoint path. The v1.1 semantic, proof,
encoding, anchor, timestamp, receipt, policy, and freshness layers are
reference-only and must not be reported as independently verified.
