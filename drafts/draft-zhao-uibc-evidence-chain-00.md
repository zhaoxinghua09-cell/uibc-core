# Agent Lifecycle Evidence Chain (UIBC)

## Package Structure, Verification, and External Anchoring

**Local draft — NOT submitted.** This document is written in Internet-Draft
shape so that reviewers can read it the way they read a draft and so that it
can be submitted unchanged if a decision is ever made to do so. It has **not**
been posted to the IETF datatracker, it carries no IETF copyright notice, and
it claims no standards status. Do not cite it as an Internet-Draft.

```
Document name : draft-zhao-uibc-evidence-chain-00
Intended status: Informational (proposed only)
Author        : X. Zhao
Version       : 00 (local, 2026-11-18)
Reference impl: https://github.com/zhaoxinghua09-cell/uibc-core
```

---

## Abstract

An autonomous agent leaves a trail of actions, but that trail is normally
produced, stored and verified by the same party it is supposed to convince.
This document specifies a portable package that binds an agent's identity,
lifecycle, and action evidence into one hash-committed structure, gives an
nineteen-check verification procedure with three-valued outcomes, and
specifies how to commit the resulting root to backends the operator cannot
rewrite. The specification is deliberately narrow: it defines what can be
checked from bytes alone, and it names what it does **not** check.

## 1. Introduction

Three problems recur when an agent's behaviour must be shown to a third party:

1. **Evidence is not citable.** Logs live in a vendor's database, in a format
   that cannot be handed over, with no way to prove that later retrieval
   returned the same bytes.
2. **Truncation is invisible.** A hash chain detects modification and
   reordering; it cannot detect deletion of a tail. A dropped tail verifies
   exactly like a shorter run.
3. **Verification is self-attested.** The party that produced the record also
   judges it, so a passing verdict carries no information.

This document answers each: a byte-level package (Section 3, 4), an
out-of-band head commitment (Section 8), and a verification procedure whose
outcomes include *inconclusive* rather than only pass/fail (Section 5).

Design rule throughout: **a verifier must never invent a fact.** Anything not
derivable from the bytes under test is reported as not-checked, not assumed.

## 2. Conventions and Terminology

The key words MUST, MUST NOT, SHOULD, and MAY are to be interpreted as
described in [RFC2119] and [RFC8174].

- **Package**: a directory of five required JSON files plus an evidence tree.
- **Evidence Root**: SHA-256 over the sorted content hashes (Section 4).
- **Seal**: a signature or MAC over the package's committed state.
- **Outcome**: `PASS`, `FAIL`, or `INCONCLUSIVE`, per check.
- **Anchored**: the root has been committed to an external backend and that
  commitment has been *confirmed* by that backend (see Section 8.2).

## 3. Package Structure

A package contains exactly:

| File | Content |
|---|---|
| `manifest.json` | `agent_id`, `agent_version`, `evidence_count`, `evidence_root`, `status` |
| `identity.json` | `agent_id`, `agent_type`, `owner`, `created_at`, `status`, `version` |
| `lifecycle.json` | ordered events, each with `event_id`, `sequence_number`, `event_type`, `timestamp`, `actor`, `previous_event` |
| `evidence/index.json` | entries: `path`, `media_type`, `content_hash`, `recorded_at`, `action_type` |
| `evidence/files/…` | the evidence bytes themselves |

Undeclared files at the package root are a structural failure (S1). Evidence
files MUST be reachable through an index entry; an unreferenced file is not
evidence.

## 4. Evidence Root

```
root = SHA-256( canonical_json( sorted( entry.content_hash for entry in index ) ) )
```

Canonical form: UTF-8, keys sorted, no insignificant whitespace, no
normalization of string values. The root is stored in `manifest.json` and is
the object that gets anchored, signed, and compared.

Because the root covers content hashes rather than paths, moving a file
without changing its content does not change the root; changing one byte does.

## 5. Verification Procedure

A verifier performs the checks below and reports one outcome per check. A
single `FAIL` makes the verdict `FAIL`; otherwise any `INCONCLUSIVE` makes it
`INCONCLUSIVE`; only all-`PASS` yields `PASS`.

| ID | Check | Notes |
|---|---|---|
| S11 | strict serialization | runs **before** any parse: UTF-8, no duplicate member names, no raw control characters |
| S1 | package structure | required files present, no undeclared root entries |
| S2 | identity consistency | `agent_id` agrees across files; enum fields valid |
| S3 | lifecycle state machine | chain valid, sequence contiguous, timestamps monotonic, actors authorised |
| S4 | evidence integrity | recompute each `content_hash` from the file bytes |
| S12 | timestamp and identifier strictness | values, not hashes: real calendar dates, lowercase UUIDs |
| S13 | merkle inclusion proofs | where the package carries them |
| S14 | strict base64 | canonical spelling, no pad-bit slack |
| S15 | anchor event resolution | where an anchor is claimed |
| S16 | external timestamp (RFC 3161) | where a token is present |
| S17 | linear receipt chain | `prev_digest` continuity, `seq` from 1, closing entry |
| S18 | policy artefact resolution | where a policy reference is present |
| S7 | evidence index metadata | index metadata digest agreement |
| S8 | package checkpoint head | recomputed checkpoint equals stored |
| S9 | head pinned out-of-band | only when the verifier was given an external head |
| S19 | freshness against a remembered head | only when the verifier keeps state: a validly signed package whose sequence went backwards is `FAIL` |
| S10 | attestation closure declared | declarations are recorded, **not** verified |
| S5 | evidence root | recomputed root equals `manifest.evidence_root` |
| S6 | seal signature | Ed25519 verified publicly; HMAC only with the owner key |

S6 is the reason the outcome set has three values: an unsigned package is
internally consistent but its provenance is unattested. Reporting that as
`PASS` would be the single most damaging mistake this document could make, so
the specification forbids it.

### 5.1 Two-implementation differential reporting

A single implementation reporting `PASS` is a claim about itself. This
document therefore requires the verification procedure to be **reported** in a
form that exposes disagreement, and defines two denominators that must travel
together:

* **disagreement over hostile packages** — of the packages the reference
  rejects, how many the second implementation calls `PASS`? A rule it does not
  implement must be answered `INCONCLUSIVE`, never `PASS`.
* **false alarms over clean packages** — of the legitimate packages the
  reference accepts, how many the second implementation rejects? Without this
  denominator, a second implementation could reach a perfect disagreement score
  by rejecting everything.

Neither number is meaningful alone, which is why they are specified as a pair
and not as a pass rate. The rules the second implementation emits that do not
map one-to-one onto a check are reported as **un-mapped** and are **not**
counted as coverage; a rule that pairs with *part* of a check is not a second
opinion on the whole check.

The machine-readable form is `uibc-differential/1`, produced by the reference
implementation's `tools/oracle_check.py --json-out <path>`. It carries the
per-case verdicts from both implementations, the exact pairs, the un-mapped
rules, the hostile split and the clean split, so that a reader can recompute
both denominators instead of trusting a summary.

### 5.2 Verdicts on a corpus the implementer does not own

Two implementations sharing an author are a differential, not an
endorsement: they can be wrong together in the same direction. Section 5.1
therefore constrains *agreement*, and this section constrains *reach*.

An implementation claiming conformance SHOULD report, per directory, the
verdicts it reaches on at least one published corpus it did not author, and
SHOULD state the corpus revision. The report has four requirements:

* **Expectation stated first.** Each directory carries the verdict its own
  publisher expects. A corpus without stated expectations measures nothing,
  because any answer can be called agreement afterwards.
* **Disagreement named, not averaged.** A run that disagrees names the
  directory and the receipt. An aggregate "97% agreement" hides exactly the
  case a reader needs.
* **Zero receipts is a failure, not unanimity.** Counting an empty run as
  agreement is how a check stops checking.
* **Granularity differences are declared.** Where the corpus publisher
  separates a core verdict from a profile verdict and the implementation
  reports one verdict, that difference is stated as a granularity difference,
  not scored as a win or a miss.

The reference implementation reports this in `uibc-aer1-corpus/1`
(`tools/aer1_corpus_matrix.py`). Measured 2026-11-19 against AER-1's
`base/test-vectors` at kit 1.5.7: 64 receipts across four directories, four
of four directories in agreement, with the single `invalid-profile` receipt
declared as the granularity difference described above.

This is a bounded claim on purpose. Judging another organisation's corpus
does not make that organisation a witness to ours; Section 8 covers external
anchoring, which is a different obligation.

## 6. Seal and Key Custody

Two seal types are defined: Ed25519 over canonical package state (publicly
verifiable), and HMAC-SHA256 (verifiable only with the owner key). A verifier
reading a public key out of the package under test proves internal
consistency only — the key could have been swapped with the content. Only an
out-of-band key (or the owner key) lifts that limitation, and even then the
result is *unanchored* until Section 8 applies.

## 7. Gate Outcomes

When a package is presented for a decision rather than a verification, the
outcome set is: `REVOKED`, `DISPUTED`, `MISMATCH`, `MALFORMED`,
`UNVERIFIABLE`. A revocation or dispute MUST name the `target_root` it
applies to and MUST be rejected if that root differs from the package's
current root — otherwise a stale revocation silently applies to new content.

## 8. External Anchoring

### 8.1 What crosses the wire

Only the root. No evidence, no inputs, no outputs, no tool names. A root is a
commitment, not a leak.

### 8.2 Two states, not one

- **pending**: a backend accepted the commitment but it is not yet confirmed
  (an OpenTimestamps calendar attestation before `ots upgrade` matures it
  into a Bitcoin commitment).
- **anchored**: the backend's confirmation has been verified.

A report MUST NOT use the word "anchored" for the pending state.

### 8.3 Backends

Two are specified because one is a single point of censorship:

- **OpenTimestamps calendars** (`POST /digests`, 32-byte body).
- **Nostr relays** (BIP-340 Schnorr signature over a NIP-01 event whose
  `content` carries the root).

Submitting to more than one backend is a SHOULD, not a MUST: availability
differs by jurisdiction.

### 8.4 The proof must not go inside the package

Recording an anchor proof as package evidence changes the package, hence
changes the root — and the root that was anchored is then no longer the root
the package has. Implementations MUST refuse to write proofs into the package
directory. This failure is silent and total; it is the single most likely
implementation error in this section.

## 9. Conformance and Interoperability

An implementation is conformant if it: (a) reproduces the committed test
vectors, (b) reports `INCONCLUSIVE` rather than `PASS` when a check cannot be
resolved, and (c) never accepts a foreign-format document as its own.

Interoperability with AER-1 receipts is defined by an explicit mapping
(Appendix A), not by similarity of intent. The reference implementation
demonstrates both directions: emitting AER-1 receipts that the AER-1
publisher's own runner accepts, and judging external AER-1 receipts
(21 valid accepted, 36 invalid rejected), with 28 documents from two unrelated
protocols rejected without exception.

## 10. Security Considerations

- **Truncation** is undetectable without Section 8; S8 catches truncation
  inside the package, S9 catches replacement by an older self-consistent
  package only when a head is supplied out of band.
- **Key substitution** is detectable only with an out-of-band or owner key.
- **Replay** of an older package is a Section 8.2 problem, not a hash problem.
- **Timestamps** are self-asserted until anchored; S12 checks that they are
  real calendar instants, not that they are true.
- **No behavioural evaluation.** This document says nothing about whether an
  agent acted well, only about whether its record is intact and attributable.
  Confusing the two is the usual overclaim.
- **Threat model boundary**: an adversary who controls the package *and* the
  backend *and* the key has won; nothing here applies.

## 11. IANA Considerations

This document requests no IANA action. No media type registration is
requested at this version.

## 12. References

Normative: [RFC2119], [RFC8174], [RFC3339], [RFC8032], [RFC2104].

Informative: [RFC3161] (external timestamp tokens, S16), [AER1] (`draft-zambo-aer1-26`,
the receipt format this mapping targets), [BIP340] (Schnorr signatures used by
the Nostr backend), [NIP01] (Nostr event serialization).

## 9.1 Carriage in a verdict record

A package verdict can be carried by a `verdict-record/1` record without changing
either format. Our three outcomes map to that record's **state** axis, not to its
`check.result` axis:

| this document | verdict-record state | why |
|---|---|---|
| `PASS` | released | all applicable checks held |
| `INCONCLUSIVE` | held | an input is missing; the claim is neither supported nor refused |
| `FAIL` | refused | a check contradicted the bytes |

Folding `INCONCLUSIVE` into `refused` would state "the evidence contradicts" where
the truth is "no evidence yet". Three rules keep the mapping honest: evidence is
cited by digest and not copied; a missing input stays `held`; a granularity
difference (one package verdict vs many per-claim records) is declared, not
scored.

## 13. Trust is a separate ladder from validity

`PASS` answers one question: is the evidence sufficient? It does not answer
whether the signer is someone the reader trusts. Conflating the two turns
`INCONCLUSIVE` into a bucket for two different problems. Three levels:

- **well-formed** — the package parses and its structure holds (no `FAIL` on the
  structural checks S1/S2/S3/S4/S5/S7/S8/S11/S12/S14);
- **valid** — the verdict is `PASS` with the key supplied;
- **trusted** — valid, and the signer's key fingerprint appears in the reader's
  trust list.

Trust is a policy input of the reader, not a property of the bytes: the same
package is trusted for one reader and not for another. A key on the trust list
does **not** make an invalid package trusted; the ladder is climbed, not bypassed.

## 14. Verification bundle

Everything a reader needs to re-check a package travels in one file, and the
owner key does not travel with it:

- the artifact digest (SHA-256 over the sorted `path\0sha256` list), file count
  and byte count;
- the verifier identity, version and spec id that produced the verdict;
- the inputs that were used (key fingerprint, expected head, whether a remembered
  state was supplied) — never the key itself;
- the verdict, trust level, per-axis outcome and first failing check;
- the anchors present in the package.

A reader holding the artifact, the bundle and their own key can recompute
everything. If the artifact changed, the bundle must refuse rather than compare.
The bundle carries claims and inputs, not secrets.

## 15. Vocabularies: informational, never a rejection

Outcome, action and disposition vocabularies are published with this document and
follow a `Specification Required` policy. A verifier **MUST NOT** reject a record
for carrying an unregistered value: registration governs shared meaning, never
acceptance. Every vocabulary check is performable from the record's own bytes.

## 16. Conformance tiers (proposal, not a claim)

_Three levels, so a deployment can say what it has rather than "we do UIBC". The
names are `uibc/core`, `uibc/witnessed`, `uibc/anchored`; a claim names the tier
and the commit. Nothing here is conformance-tested yet: the tiers describe
requirements, and no vectors exist for them._

| Tier | Adds on top of the previous | Runnable check |
|---|---|---|
| `uibc/core` | the 19 checks pass on the package; verdict is one of PASS / FAIL / INCONCLUSIVE; no dimension merged | `uibc verify` |
| `uibc/witnessed` | a verification bundle is emitted; the reader's trust list is separate from the artifact; the head is co-signed by two distinct keys | `--bundle-out`, `--trustlist`, `tools/cosign_head.py verify` |
| `uibc/anchored` | the anchor is `anchored`, not `pending`; the head carries the tree size inside the signature; successive heads only grow and a new size means a new root | `tools/cosign_head.py chain` |

Three rules bind the tiers, and each closes a gap someone else left open:

1. **The size is signed, not asserted.** A head that states a tree size without
   covering it with a signature lets the size be swapped after signing; the
   signature then still verifies. The tree size sits inside the signed
   statement, and a swap fails verification.
2. **Only-grew is checked, not assumed.** An inclusion proof shows one leaf; it
   says nothing about what the log used to be. A chain of heads must show
   non-decreasing size, a different root whenever the size grows, and never two
   different roots at one size. The decision-provenance draft states that its
   anchoring extension does not yet check this; a tier that claims `anchored`
   must.
3. **A tier is never a trust claim.** `uibc/anchored` says the evidence chain
   holds, not that the record is true or that the issuer is trusted; that stays
   the reader's trust policy (Section 13).

## 17. `pending` as a named absence (proposal — not implemented)

_This section exists because the anchored vectors need a wire form for "not yet
anchored". It is a **proposal**: the verifier reads `evidence/anchors.json` with
resolver `evidence-merkle` today, and does **not** read a `state` field. No
vector may claim anything under this section until the checks below exist._

### 17.1 The object it extends

Existing form, unchanged and still the default:

```json
{"resolver": "evidence-merkle", "anchors": [
  {"id": "anchor-001", "version": 1,
   "leaf_hash": "<64 lowercase hex>",
   "anchored_at": "<RFC 3339 with zone>",
   "root": "<64 hex>", "size": 3, "index": 1,
   "proof": ["<64 hex>", "..."]}]}
```

Proposed additions, all optional, so existing packages and the 30-case corpus
keep their meaning:

| field | values | required when |
|---|---|---|
| `state` | `anchored` (default when absent) / `pending` | always readable |
| `submitted_to` | `ots` / `nostr` / `tsa` | `state` is `pending` |
| `absent_reason` | `not-submitted` / `submitted-no-receipt` / `receipt-withheld` | `state` is `pending` |
| `resolves_externally` | `true` only when a receipt verifies against a public log | `state` is `anchored` |

`pending` carries no `root`, `size`, `index` or `proof`; if any of them appear
alongside `state: pending`, the record is rejected rather than reconciled.

### 17.2 The four checks this section would require

1. **Unsupported is a rejection; missing is an INCONCLUSIVE.** Measured on
   2026-11-25: changing a package's `resolver` from `evidence-merkle` to
   `sigstore` makes the verdict FAIL, because we cannot resolve it. That is the
   right answer for an algorithm we do not support — the MMR receipts profile
   requires rejecting a receipt whose `vds` the verifier does not support, and
   "I do not implement this" is not "this is false". What must reach
   INCONCLUSIVE is a different case: an anchor that **claims** to be anchored
   but carries no receipt the reader can check (`state: pending`) — missing
   evidence, not contrary evidence. A receipt that verifies but covers another
   head is FAIL, as rule 3 says: that is evidence to the contrary.
2. **`pending` never yields PASS under `strict`.** Absence of a receipt is not
   evidence against the record, and it is not evidence for it either.
3. **`anchored` must carry a receipt whose chain reaches `head`.** A receipt
   that verifies but covers a different head is FAIL — evidence to the contrary,
   not missing evidence.
4. **An unknown `state` is rejected.** `state` decides whether a verdict may be
   PASS at all, so Section 15's "unregistered value is informational, never a
   rejection" does not apply to it.

### 17.3 Time is not implied
`anchored_at` records what the producer says. It is not a time bound: only an
RFC 3161 token from an authority the reader trusts gives one, an OTS proof shows
only that the bytes existed before a block was mined, and a receipt of
registration states no time at all.

### 17.4 To implement, in order

1. read `state` in `uibc_core/anchor.py`, default `anchored`;
2. add the four rejections of 17.2 as distinct problems, not as generic
   "unresolvable";
3. pin the current verdict for an unresolvable anchor with a vector;
4. build AC2 / AC4 / AC5 on top of a real fixture;
5. only then name the tier in Section 16.

### 17.5 How this maps onto HALT and REJECT

Two words from the formal literature are worth borrowing, because they name a
distinction this document has so far made by habit:

- **HALT** — a required input is unavailable, so **no epistemic verdict is
  produced**. Our INCONCLUSIVE is the informal counterpart.
- **REJECT** — the check was performed and the record went against it. Our FAIL
  is the informal counterpart.

The distinction this forces into the open: a verifier that does not implement a
named scheme is **not** producing contrary evidence. Whether that is HALT or
REJECT is a **policy choice**, and this document chooses REJECT, matching the
MMR receipts profile's requirement to reject a receipt whose VDS is unsupported.
To keep that choice from erasing the distinction, the verifier now carries a
report-level `unsupported` list naming the checks that failed this way: the
verdict stays FAIL, but a reader can separate "could not check" from "checked and
refused". This is the minimum other drafts already require of themselves
(`draft-gruszka-scitt-statement-identification-04` reports UNSUPPORTED as its own
class; `draft-nestorov-scitt-p10-underdetermination-03` HALTs), and until this
field existed no claim here could honestly be read as "cannot check".

## Implementation Status

_As of 2026-11-25, repository `232deb4`, reference verifier 0.5.5._

- Implemented and re-runnable: the 19-check procedure, the 58-case corpus with a
  validator, anchor handling (OpenTimestamps + Nostr, `pending` vs `anchored`),
  the differential report with two denominators, the per-axis report
  (`tools/axis_report.py`), the verification bundle (`--bundle-out`), the reader
  trust ladder (`--trustlist`), and head co-signature by two distinct keys
  (`tools/cosign_head.py`).
- Prototyped outside the published CLI: nothing above; all of it is behind a flag
  or a tool that leaves the default verdict unchanged. None of it carries its own
  vectors yet, so no conformance claim is made for the new flags.
- Not implemented: a witness seat that is not the owner (the co-signature demo
  uses two synthetic keys), and registration of the trust-list format.
- This document remains a local draft: it is not in the IETF archive, carries no
  IETF copyright notice, and claims no standards status.

## Appendix A. Relationship to AER-1

| Aspect | AER-1 | This document |
|---|---|---|
| Unit | one receipt per execution | package: identity + lifecycle + many evidence items |
| Root | Merkle root over step receipt ids | SHA-256 over sorted evidence content hashes |
| Outcome set | accept / reject | PASS / FAIL / INCONCLUSIVE |
| Missing metadata binding | MUST fail (Section 6), not implemented by the publisher's runner | n/a |
| Anchoring | section defined, SDK ships Nostr + OTS | two backends specified, both implemented |

Three claimed spec-versus-corpus divergences were re-audited against the
specification text; two hold (mandatory `metadata_hash` for 0.4 receipts;
integer-valued floats accepted for `seq` but rejected for `entry_count`), and
one was withdrawn as an error of ours. See `docs/AER1-SPEC-AUDIT.md`.

## Appendix B. Test Vectors and Re-running

Reproduction commands live in the reference implementation: `tools/aer1_spec_audit.py`
(corpus audit), `tools/aer1_interop_demo.py` (end-to-end interop),
`tools/anchor_chain_head.py` (OTS), `tools/nostr_anchor.py` (Nostr, checked
against the official BIP-340 vectors committed at `tests/data/bip340-vectors.csv`).

## Appendix C. If This Is Ever Submitted

Nothing in this repository submits it. Doing so would require: an author
email registered with the datatracker, `xml2rfc`-valid source, a chosen
working group or an AD sponsor, and an IPR declaration. Until all four exist,
this file stays a local draft, and any claim that it is "an I-D" is false.
