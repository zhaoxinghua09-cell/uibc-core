# Crosswalk: standards layer vs uibc-core checks

Status date: 2026-11-21.
Scope: map the clauses that actually matter for "agent behaviour evidence" onto what
`uibc_core.verify` and the shipped tooling do **today**. Nothing here claims
conformance, alignment, or certification. Every cell says what exists, what does
not, and where the source could not be verified first-hand.

This document exists because our older crosswalks covered *peer drafts*
(`CROSSWALK-ASQAV-COMPLIANCE.md`, `AER1-CROSSWALK-RESULT.md`) but not the
**standards layer** reviewers quote back at us. Reading a standard is not the
same as aligning with it; this file keeps those two things separate.

## How to read the verdict column

- **covered** — an equivalent mechanism exists, runs, and has a test that fails if it stops.
- **partial** — mechanism exists for our envelope shape but not the standard's wire format,
  or only one of N sub-requirements is met.
- **gap** — not implemented.
- **n/a** — the standard's requirement is out of scope for this tool by design (say why).
- **UNVERIFIED** — the standard's text or status could not be retrieved first-hand; no
  alignment claim is made, and the cell must not be quoted as green.

## A. SCITT — RFC 9943 (IETF, Standards Track, real)

Source: <https://www.rfc-editor.org/rfc/rfc9943.html>. Companion: RFC 9942 (COSE receipts).
This is the only item in this matrix that is a published Standards Track RFC.

| RFC 9943 requirement (source text) | Our mechanism | Verdict | Boundary |
|---|---|---|---|
| "issues a receipt" to the registrant | `emit_receipt.py` / S6 Ed25519 seal over the signed envelope | partial | Our receipt is our envelope shape, not a COSE Receipt (RFC 9942). We do not emit COSE_Countersign / the SCITT `receipt` CBOR structure. |
| "linear and irrevocable history" | `uibc_core/chain.py` S17 — genesis is 64 zeros, each link is SHA-256 over JCS of predecessor envelope; edited/dropped/reordered/empty all tested FAIL | covered (our shape) | Linear and append-only for our chain; "irrevocable" in SCITT's transparency-log sense is not claimed. |
| "proof that signed statements were recorded" | RFC 3161 token (S16, verified offline, CA provenance written down) + Merkle root/inclusion (RFC 6962, 29-vector corpus) | partial | We prove an artifact was timestamped and a leaf was in *our* tree. The Rekor inclusion proof against the *public* log does **not** verify in either implementation — see `EXTERNAL-ANCHOR.md`. That row is red. |
| Transparency service with signed checkpoints | No transparency-service component; `registry_server/` serves certificates/revocations/disputes only | gap | A hosted transparency log is not shipped. Do not describe the registry server as a SCITT transparency service. |
| Content-addressed, verifiable data structure (Merkle) | RFC 6962 tree, leaf=SHA-256(0x00‖leaf), node=SHA-256(0x01‖L‖R), odd tail promoted; `l01`–`l05` vectors | covered | Verified by a checker that imports nothing from uibc_core (29/29). |

**Honest line:** we implement the *properties* SCITT names (receipt, linear history,
Merkle inclusion) in our own wire format. We are not a SCITT implementation and
must not say we align with RFC 9943.

## B. W3C Verifiable Credentials — Data Integrity EdDSA Cryptosuites v1.0

Source: W3C Recommendation 2025-05-15 (`eddsa-jcs-2022`). First-hand status: the
Recommendation is published; the suite name and status are stable.

| Requirement | Our mechanism | Verdict | Boundary |
|---|---|---|---|
| Ed25519 over canonicalized document (JCS/RDFC) | S11 strict serialization + S6 plain RFC 8032 Ed25519; `receipt_digest`/`policy_digest` vectors hash RFC 8785 JCS bytes | partial | We use RFC 8785 JCS, not RDF Dataset Canonicalization. Not a VC Data Integrity implementation. |
| Suite identifier `eddsa-jcs-2022` in proof | We do not emit VC proof blocks or suite identifiers | gap | No VC issuance/verification path. |
| Verification method resolved from DID / controller document | S2 pinned-key mode; swapping + re-signing fails when key pinned (RT12) | partial | Pinning is a mechanism, not DID resolution. The registry form the VC model assumes is absent. |

## C. OWASP AISVS v1.0 (191 requirements)

Source: OWASP AISVS 1.0 (published). We did **not** retrieve and read all 191 items
one by one; this row maps the categories that touch evidence, not a full audit.
Claiming "aligned with AISVS" would be false at this point.

| AISVS area | Our mechanism | Verdict | Boundary |
|---|---|---|---|
| Log/record integrity for agent actions | S1–S18 checks on packages, three-valued verdict (PASS/INCONCLUSIVE/FAIL) | partial | We verify evidence packages; we are not an application of the whole AISVS control set. |
| Cryptographic integrity of stored records | Ed25519 seal, SHA-256 chain, RFC 6962 Merkle, RFC 3161 token | covered (our shape) | Same envelope-shape boundary as above. |
| Key management / rotation | Key generation, pinned-key mode; `timestamps/` key handling | partial | No rotation/revocation lifecycle in the verifier. |
| Failure handling / negative controls | `failure_corpus/` F-001–F-006 with reproduction steps | covered (practice) | This is our engineering practice, not an AISVS control implementation. |

## D. EU AI Act — Article 12 (record-keeping)

Source status: Regulation (EU) 2024/1689 general application date 2026-08-02.
**Regulation (EU) 2026/1744 (Digital Omnibus on AI, OJ 2026-07-24, in force 2026-07-27)
changed the timetable** — high-risk obligations moved to 2027-12-02 / 2028-08-02.
Whether Art.12 or Art.55 was individually amended was **not verified from the
official text** (EUR-Lex retrieval returned empty). Do not write "Art.12 applies
since 2026-08-02" as a verified fact.

| Relevant requirement | Our mechanism | Verdict | Boundary |
|---|---|---|---|
| Automatic event logging over the system lifetime | Receipt chain + evidence packages record agent actions | partial | A package is not a lifetime log; continuity across deployments is not proven. |
| Traceability of inputs, outputs, context | Evidence package links change → evidence → handover (see `examples/`) | partial | Coverage is our example flows, not the full Act's scope. |
| Log integrity / tamper-evidence | S1–S6 verdict matrix: tampered/deleted/duplicated/reordered FAIL | covered (our shape) | 24/24 fixture cells match EXPECTED; this is tamper-evidence of the package, not legal compliance. |
| Retention period | no retention enforcement in the tool | gap | The ASQAV draft's 1825-day floor is likewise not met. |

## E. ISO/IEC 24970 (AI system logging) and ISO/IEC 42001 (AIMS)

Source status: **ISO/IEC 24970 is at stage 60.00 "publication"** — not a draft,
not a published standard yet. No cell may be read as alignment.
ISO/IEC 42001 is published; it is a management-system standard, not a technical
log format, so most rows are n/a.

| Item | Verdict | Note |
|---|---|---|
| ISO/IEC 24970 logging requirements | UNVERIFIED → **no alignment claim** | Text not retrieved first-hand; stage 60.00. Our 2014-vs-2025 GMP comparison work is separate and must not be conflated. |
| ISO/IEC 42001 AIMS processes | n/a | Management-system scope. We provide technical evidence tooling that *could* feed an AIMS; we do not implement one. |
| NIST AI RMF 1.0 / GenAI Profile | n/a (voluntary framework) | No "evidence chain" mandate we could map to. Do not quote as alignment. |

## F. Why this matrix is itself an asset

Every peer we benchmarked publishes PASS counts. None of them publishes a
standard-by-standard map that says **gap / partial / UNVERIFIED** in the same row
as the mechanism. This matrix is not proof of compliance; it is a falsifiable
record of exactly where we are silent. It replaces "we reference the standards"
with "here are the cells we cannot fill".

Corrections carried in from the 2026-11-21 first-hand verification round:

1. Tracekit: arXiv v2 abstract says **two** independent verifier implementations
   (Python, TypeScript; browser page is the TS form). README mirror says 1.5.3 vs
   abstract 1.4.1 — version drift, preprint, author-reported numbers.
2. Treeship: ecosystem-map's `v0.31.14` appears in no first-hand source; official
   confirms only to 0.31.2; 0.31.1 and earlier had a `package verify` false-green
   defect (TS-2026-002). Version string in `ECOSYSTEM-MAP.md` must be corrected.
3. Vaara: latest version unresolved (1.78.0 / 2.5.0 / 2.17.0 conflict, PyPI
   CAPTCHA); license changed Apache-2.0 → AGPL-3.0-or-later; "second independent
   implementation reproduces vectors" has no findable repository — do not cite.
4. AgentNotary: author's personal GitHub only (self-reported); no institutional
   first-hand source; do not cite its numbers.
5. EU AI Act: general date 2026-08-02, but (EU) 2026/1744 moved high-risk dates;
   Art.12/55 per-article impact UNVERIFIED.

## Boundary

Written from first-hand standard sources where retrievable plus our own code and
measured runs. Rows marked UNVERIFIED or gap are deliberate. This document is an
internal judgement aid containing competitive assessment — **do not publish
externally without review**. Every cell can be checked against the cited source
and the named command in `conformance.md`.
