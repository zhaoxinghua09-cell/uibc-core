# Interop matrix: can we verify their receipts, can they verify ours?

<!-- facts: current -->


Status 2026-11-17. Method, stated first because it bounds every cell:

* every peer row is built from **their published specification text**, not from a
  running installation. We did not install NovaFabric (no public package), we did
  not run Vaara or agent-receipts on this machine. Cells that would require
  running their code are marked **not tested**, not "works".
* the "our verifier on their shape" column was produced by feeding a receipt
  built from their documented fields into `uibc_core.compliance.verify_receipt`
  (see `tests/test_v14_interop_matrix.py`). Those samples are **synthetic**:
  field names and nesting follow their docs, values are ours. A synthetic sample
  can only show *where our verifier stops*, never that their real output passes.
* "they verify ours" cannot be tested from here at all: none of these tools is
  installed and neither NovaFabric nor Vaara ships a verifier we could run. Every
  cell in that column is **not tested**.

## The three shapes

| project | envelope | signature | time anchor | log | chain | policy digest |
|---|---|---|---|---|---|---|
| **us** (`uibc_core`) | package + optional ASQAV-shape receipt | Ed25519 over DSSE PAE of JCS payload | RFC 3161 (verified) + OTS (pending) | Rekor entry written, inclusion **not verified** | `previousReceiptHash` over JCS (S17) | `policy_digest` resolved against shipped artefact (S18) |
| **NovaFabric** | DSSE (in-toto style), ECDSA P-256 | DSSE envelope, alg pinned by verifier policy | RFC 3161 | append-only Merkle log + witness cosigning + MMR | per-capsule Merkle root (RFC 6962 style) + lineage edges | `policy event` entity, no digest-resolution facility described |
| **agent-receipts** | flat JSON receipt (`v`, `id`, `ts`, `agent`, `principal`, `action`, `sig`) | Ed25519, `sig.alg` in envelope | none (roadmap Phase 6) | none (roadmap Phase 6) | `chain` id for causal grouping, no predecessor hash in the documented shape | none |
| **Vaara** | hash-chained audit record + export signature | signature at export | none described | none described | hash chain over records | policy gate decision recorded, no digest field |

## Verification of their receipts by us (synthetic samples)

| peer | what our verifier does with a doc-shaped receipt | where it stops | honest reason |
|---|---|---|---|
| agent-receipts | rejects | `type`, `issuer_id`, `action_ref`, `policy_digest`, `payload_digest`, `previousReceiptHash` all missing | their receipt is a *per-tool-call* record; ours is a *per-action compliance receipt*. Different objects, not different quality. |
| NovaFabric | rejects | envelope is DSSE with `payload`/`payloadType`/`signatures`, not a JCS body with `signatureObject`; no `previousReceiptHash` field | we could verify their **signature** if we implemented DSSE parsing; we cannot verify their **capsule semantics** without their fifteen-entity schema. |
| Vaara | rejects | no REQUIRED field set; signature is over an export blob, not over a receipt body | their model is a hash-chained trail, not a signed receipt per action. |

**Reading this correctly:** three rejects is not "we beat them". It is "our verifier
only understands the ASQAV shape, and each peer invented a different shape". The
work that would matter is an adapter per peer, and that needs their real samples,
which we do not have.

## Verification of our receipts by them

**Not tested, for all three.** NovaFabric's paper is explicit that its offline
verification path "has not yet been exercised by an independently implemented
verifier", and that "neither a second implementation nor that corpus exists yet".
agent-receipts publishes a spec with eight conformance vectors and a Python
reference implementation, which is more than we publish in that dimension - our
tests are not a language-neutral conformance corpus. Their corpus, so that a
reader does not have to take our word for it: the npm README states the format is
specified in `spec/v0.1/SPEC.md` with 8 conformance vectors and a Python reference
implementation — <https://www.npmjs.com/package/agent-receipts-cli>. Read
`spec/v0.1/SPEC.md` at the commit you check out; the count is their claim, and we
did not run their vectors.

## What this matrix says about "beating the competition"

1. **NovaFabric is ahead on**: session-level replay (four modes), redaction
   attestation, witness cosigning, MMR, did:key, maker-checker, and a
   fifteen-entity schema. Its own text also says its third-party verification is
   unexercised, which is the same position we were in before this week.
2. **agent-receipts is ahead on**: being at the interception point (MCP proxy,
   zero code change) and on publishing an independent conformance corpus.
   It is behind on: anchoring, policy digest, chain linkage - all "roadmap".
3. **Vaara is ahead on**: policy enforcement at the call site and EU AI Act
   Article 12 framing. Behind on: cryptographic structure of the record.
4. **We are ahead on**: a public repository an outsider can clone and run
   (594 tests, 15 red-team scenarios, 36 attacks, all re-run from a fresh anonymous clone), a
   published crosswalk to an IETF draft with the failing cells written down, and
   a habit of publishing our own failed verification attempts (Rekor inclusion
   proof) with the third-party cross-check that also failed.

The differentiator is not a feature. It is that **our claims are already
exercised by someone who is not us**, and we publish the parts that do not work.

**The failed inclusion proof is a defect, not a policy.** It is written down because
hiding it would make every other number here unverifiable; it is not a design position,
and it is not "expected failure". The fix path is an adapter written against the log's
documented proof format, and until that exists this row stays red. Reading this file
should not leave the impression that a failing proof is acceptable output.
That is rarer than any of the technical cells above.

**On the corpus dimension, as of 2026-11-17.** agent-receipts publishes a spec with 8
vectors plus a Python reference implementation; we now publish 15 vectors
(`docs/conformance/vectors.json`) **but no second implementation**. Two of the three
steps — canonical bytes and Ed25519 — are checkable by anyone holding the file plus
`cryptography` (`tools/conformance_check.py`, 15/15 from a checker that imports nothing
from this project). Receipt structure, chains, anchoring and policy are **not** in the
corpus. Closer, not parity; the difference is stated, not smoothed (`docs/CONFORMANCE.md`).

## What would move the needle next

| action | needs | closes |
|---|---|---|
| run their real samples through an adapter | install Vaara / agent-receipts; NovaFabric sample from authors | three "not tested" cells |
| extend the corpus to receipt structure, chains and anchors | us only | the rest of the dimension where agent-receipts and Tracekit are ahead |
| a verifier written by someone who is not us | a third party | the "second implementation" gap, which 15 vectors do not close |
| MCP interception point (proxy that writes our receipts) | us only, larger build | Vaara's advantage |
| replay protocol | us only, much larger | NovaFabric's advantage |
