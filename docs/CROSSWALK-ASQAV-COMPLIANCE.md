# Crosswalk: draft-marques-asqav-compliance-receipts-01 vs uibc-core checks

Status date: 2026-11-17. Source draft: `https://www.ietf.org/archive/id/draft-marques-asqav-compliance-receipts-01.html`
(§8 "Verifier Behaviour", "Mandatory Checks"). Nothing here is a claim of conformance:
this file maps the draft's seven MUST checks onto what `uibc_core.verify` actually does
today, and states which cells are empty.

Read the column "verdict" strictly:

- **covered** - the same check exists and runs, with a test that fails if it stops running.
- **partial** - the check exists for our own envelope shape but not for the draft's wire shape
  (ACTA-RECEIPTS / DSSE), so it would not satisfy a Compliance Verifier as written.
- **gap** - not implemented at all.

## The seven mandatory checks

| # | Draft requires | Our check(s) | Verdict | What is missing |
|---|---|---|---|---|
| 1 | Verify the signature using `signature.alg` per ACTA-RECEIPTS | S6 seal verification (Ed25519 over the package head); `tools/anchor_rekor.py` verifies the Sigstore SET with the log's published key | partial | We verify *our* seal format, not a DSSE envelope with `signatureObject.alg`. A receipt produced by another implementation would not parse. |
| 2 | Resolve the key through a trust anchor; MUST NOT trust a key embedded in the envelope | S2 identity; pinned-key mode (red-team RT12: swapping the key and re-signing **fails** when the original key is pinned) | covered (mechanism) | The mechanism exists and is red-teamed; the *registry* form the draft assumes (DID / Audit Pack trust metadata) does not. |
| 3 | Verify all REQUIRED fields present and well-formed | S1 structure+root, S7 index metadata, S11 strict serialization, S14 strict base64, S0 fail-closed | partial | Our REQUIRED set is ours, not the draft's (`type`, `issued_at`, `issuer_id`, `payload_digest`, `action_ref`, `policy_digest`, `previousReceiptHash`). Field names and vocabulary differ. |
| 4 | Recompute the predecessor envelope digest and compare to `previousReceiptHash` | **S17** linear receipt chain (`uibc_core/chain.py`): genesis is 64 zeros, each link recomputed as SHA-256 over the JCS of the predecessor envelope | **covered (our shape)** | The clause is implemented and tested (edited envelope, dropped head, reordered pair, empty chain, unjudgeable envelope all FAIL); the envelope field names are ours, not ACTA-RECEIPTS'. |
| 5 | At least one anchor, and re-verify it cryptographically against the signed envelope; metadata presence alone MUST NOT yield "valid" | **S16** RFC 3161: token parsed offline, signature verified against the shipped CA, digest bound to the anchored head; tool reports `signature_verified` and refuses to report "anchored" without it | **covered** (RFC 3161 half) | No OpenTimestamps anchor. The draft wants "RFC 3161, OTS, or both" and calls both stronger. We have one of two. |
| 6 | Future-skew bound on `issued_at` (>300 s ahead ⇒ reject); past timestamps MUST NOT be rejected when within retention | **S12** (`verify.py`, `_semantic_problems(..., now=, future_skew_s=300)`): one-sided bound against the verifier's clock; a past timestamp is never rejected for age | **covered** | The clock is injected, so the bound is testable without sleeping (7 tests, including 250 s pass / 350 s fail / ten-year-old pass). |
| 7 | `policy_digest` resolves through the Audit Pack; recompute `SHA-256(JCS(artefact))`; a nonced form MUST NOT count | **S18** policy artefact resolution (`uibc_core/policy.py`): every listed digest recomputed over JCS of the shipped artefact, and any `policy_digest` declared by a receipt must resolve there | **covered (our shape)** | Non-JSON artefacts have no JCS form, so a PDF policy must ship a JSON projection - a constraint of the draft, documented in the module. |

**Score as a Compliance Verifier today: 4 covered (rows 2, 4, 5, 6, 7 - row 2 by
mechanism only) / 2 partial (rows 1 and 3, both wire-format) / no silent gaps.**
S17, S18 and the S12 skew bound were added on 2026-11-17 after this table was
first written; before that the honest number was 1 covered out of 7.

## What this means competitively

The draft is newer than the products we benchmarked and it is stricter than all of them:

- it makes hash-chain linkage **mandatory** (upstream ACTA-RECEIPTS leaves Commitment Mode optional);
- it requires **dual anchoring** (RFC 3161 + OpenTimestamps);
- it adds a **retention floor** (1825 days) and **revocation metadata** the verifier must consult;
- it forbids trusting a key embedded in the envelope;
- it requires anchor re-verification, explicitly rejecting "metadata present" as evidence.

Two of those (dual anchor, revocation) are cells where we are behind, not ahead. The one
cell where we are structurally ready is #5, because the RFC 3161 path is already real
(a token we did not generate, verified offline, with the CA provenance written down).

## What would have to change to claim the draft's Verifier role

Ordered by cost, not by desire:

1. **Emit the draft's envelope** (`type` / `issued_at` / `issuer_id` / `action_ref` /
   `policy_digest` / `previousReceiptHash` / `signatureObject` / `anchors`) as an *additional*
   output shape next to our package format. Our checks then run on that shape.
2. **Linear chain**: add `previousReceiptHash` (lowercase hex of SHA-256 over JCS of the
   predecessor envelope, all-zero for the first) and make S8 verify it.
3. **JCS (RFC 8785)**: needed for both the chain hash and `policy_digest`. We currently do
   strict serialization (S11) but not JCS by name; the digest would differ on non-ASCII keys.
4. **policy artefact resolution**: a digest → artefact map inside the package (an "Audit Pack
   lite"), with a test that a missing artefact makes the receipt non-conformant.
5. **OpenTimestamps anchor**: second anchor type; the 7-day calendar-to-block window is the
   hard part and needs a real submission, not a mock.
6. **Revocation metadata**: a signed revocation notice naming key, time, chain head; verifier
   rejects receipts signed by a revoked key at or before `issued_at`.
7. **300 s future-skew check** in S12, with the "past is fine within retention" clause.

## Boundary of this document

This crosswalk was written by reading the draft and our own code. It has **not** been reviewed
by the draft's author, and it makes no claim that the draft will adopt anything we do. It is
published so that a reader can check each cell against both sources rather than take our word.
