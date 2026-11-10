# Verdict and Seal Semantics — seal v0.3

Status: PROPOSAL, as is everything in this repository. This document is the
normative statement of what a uibc-core verification verdict *means* in
v0.3. It exists so that the semantics live in a specification, not in the
reference implementation's control flow: a second implementation (see
`independent_verifier/`) is written against this text, and the fixture
matrix (`fixtures/EXPECTED.md`) pins the agreed outcomes. If an
implementation and this document disagree, that is a defect in one of
them — report it.

## 1. The three-valued verdict

Verification runs six checks (S1 structure, S2 identity consistency,
S3 lifecycle state machine, S4 evidence content hashes, S5 evidence root,
S6 seal signature). Each check ends PASS, FAIL, INCONCLUSIVE, or — only
where a check does not apply at all — SKIP.

The top-level verdict is:

| Condition | Verdict |
|---|---|
| any check FAIL | **FAIL** |
| else, any check INCONCLUSIVE | **INCONCLUSIVE** |
| else | **PASS** |

PASS is therefore reserved for packages where *every* applicable check
was actually resolved. An unresolved check can no longer ride under a
top-level PASS.

### Why this changed (v0.2 → v0.3)

Through v0.2 the verdict was two-valued: PASS unless some check FAILed.
S6 in open mode (no key) was INCONCLUSIVE, and that fact was stated in
the report's detail lines — but any consumer reading only the top-level
verdict saw PASS. An external review (2026-11) demonstrated the
consequence concretely: a fully self-consistent forgery — evidence
rewritten, index hashes and evidence root recomputed — verified PASS in
open mode, because nothing in the package could contradict it and the
one check that spoke to provenance was unresolved. The detail line was
honest; the verdict was misleading. v0.3 fixes the verdict.

Exactly three fixture cells changed, all in open mode, all at the
top level only (no individual check outcome moved):

| Fixture | v0.2 | v0.3 |
|---|---|---|
| clean (HMAC-sealed), open mode | PASS | INCONCLUSIVE |
| malicious (self-consistent forgery), open mode | PASS | INCONCLUSIVE |
| malicious-keyswap, open mode | PASS | INCONCLUSIVE |

The forgery is still not *detected* without a key or a usable public
seal — that boundary is unchanged and stated in §4. What changed is that
it no longer receives a verdict indistinguishable from a verified
package.

## 2. Seal algorithms

A seal lives at `signatures/seal.json` and signs the canonical
serialization of `{"identity": ..., "manifest": ...}` — and nothing
else. The manifest in turn binds the evidence root (§3), so evidence
content is covered transitively: one level of indirection, stated
plainly.

### 2.1 HMAC-SHA256 (v0.2, retained)

Symmetric: the same secret signs and verifies. A verifier needs the
owner's key (`--key`, "strict mode"). Without it, S6 is INCONCLUSIVE —
a symmetric seal cannot be checked publicly, by construction.

### 2.2 Ed25519 (v0.3, new)

Asymmetric, per RFC 8032, implemented in pure Python on the standard
library only (this project remains zero-dependency). The seal records:

- `algorithm`: `"Ed25519"`
- `public_key`: base64 of the 32-byte public key
- `key_id`: SHA-256 hex of the public key
- `signature`: base64 Ed25519 signature over the seal payload

Because the public key travels with the package, **anyone can verify an
Ed25519 seal without any secret, in every mode**. S6 resolves to PASS or
FAIL, never INCONCLUSIVE, for a well-formed Ed25519 seal. Provenance
verification stops being a permissioned act: no key exchange, no owner
involvement, no account.

Key files: `uibc keygen --ed25519 --out owner.key` writes the seed file
(text: `ed25519:` + hex seed — a secret) and `owner.key.pub` (hex public
key — publishable). `uibc submit --key owner.key` detects the format
and seals accordingly.

**Substitution and pinning.** A substituted Ed25519 key produces a seal
that is valid *against its own key*: unpinned open verification of an
attacker-resealed package returns PASS, because the seal genuinely
attests "whoever holds this key sealed this content". To bind a package
to a *known* signer, pin the expected public key:
`uibc verify --pubkey owner.pub`. A seal whose recorded public key
differs from the pin FAILS S6. Pinning is the verifier's half of the
contract; publishers should make their public key findable (e.g. in the
repository, the registry entry, or the paper trail) so verifiers can
pin it. The recorded `key_id` makes a mismatch visible at a glance.

**Implementation note.** The pure-Python Ed25519 is not constant-time.
It is correct — locked to the RFC 8032 §7.1 vectors by
`tests/test_seal_v03.py` — and adequate for sealing short payloads at
package-submission rates. Deployments needing side-channel resistance
at volume should substitute a native implementation behind the same
interface.

## 3. What the evidence root binds — and what it does not

`evidence_root = SHA-256(canonical(sorted(content_hashes)))`. It binds
the **set** of evidence content hashes. It does **not** bind:

- **Order.** Reordering entries in `evidence/index.json` leaves the root
  unchanged and verifies PASS. Entry order is presentation, not
  attestation. (Lifecycle *event* order is a different matter: it is
  checked by S3.)
- **Timestamps.** No timestamp in a package is anchored to an external
  time source; treat all package times as claims by the package author.
- **Lifecycle event signatures.** `event.signature` remains unratified
  and is **not** covered by the seal. S3 checks the state machine, not
  per-event signatures.

## 4. Assurance levels

Every report carries an `assurance` field summarising what the seal
established:

| Value | Meaning |
|---|---|
| `public-key` | An Ed25519 seal verified. Provenance is third-party attested (subject to the pinning contract in §2.2). |
| `owner-key` | An HMAC seal verified against the owner key in strict mode. Provenance attested to whoever holds that key — symmetric, so the attestation cannot be relayed to a third party. |
| `unattested` | No seal could be verified in this run (unsigned, or an HMAC seal checked without its key). The package may be perfectly consistent; its provenance is unestablished. |

## 5. Mode summary

| Package | Open (no key) | Strict (`--key`) | Pinned (`--pubkey`) |
|---|---|---|---|
| Unsigned | INCONCLUSIVE | FAIL (S6) | INCONCLUSIVE |
| HMAC-sealed, intact | INCONCLUSIVE | PASS | n/a |
| HMAC-sealed, forged manifest | INCONCLUSIVE | FAIL (S6) | n/a |
| Ed25519-sealed, intact | **PASS** | mode mismatch FAIL (S6) | PASS if pin matches |
| Ed25519-sealed, re-sealed by attacker | PASS (attacker's key) | mode mismatch FAIL (S6) | **FAIL (S6)** |
| Any package, evidence tampered | FAIL (S4) | FAIL (S4) | FAIL (S4) |

Reading this table is the whole threat model. Everything not covered
here is not claimed.
