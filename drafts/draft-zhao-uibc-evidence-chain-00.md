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
This document specifies a portable package for an agent's identity, lifecycle
events, and action evidence; a nineteen-check verification procedure with
three-valued outcomes; a seal over the committed state; and a way to commit one
root to external backends the operator does not control. The commitments are not
interchangeable: the anchored root covers evidence content hashes only, while
identity and lifecycle are bound by the seal and the head (Section 4.1 states
exactly what commits what, and what commits nothing). The specification is
deliberately narrow: it defines what can be checked from bytes alone, and it
names what it does **not** check.

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
an out-of-band head (Section 16) and an anchor commitment (Section 8), and a
verification procedure whose
outcomes include *inconclusive* rather than only pass/fail (Section 5).

Design rule throughout: **a verifier must never invent a fact.** Anything not
derivable from the bytes under test is reported as not-checked, not assumed.

## 2. Conventions and Terminology

The key words MUST, MUST NOT, SHOULD, and MAY are to be interpreted as
described in [RFC2119] and [RFC8174].

- **Package**: a directory of five required JSON files plus an evidence tree.
- **Evidence Root**: SHA-256 over the sorted content hashes (Section 4).
- **Seal**: a signature or MAC over the package's committed state.
- **UIBC**: the name used in this document for the package format and its
  verification procedure; it is a local working name, not a registered
  vocabulary term, and it expands to nothing.
- **Outcome**: `PASS`, `FAIL`, or `INCONCLUSIVE`, per check.
- **Head**: the signed statement of Section 16 over the root, the tree size, the
  signer's `role` (`owner` or `witness`, and the two roles must use distinct
  keys), and optionally the verifier identity `vds`. A head is not a package
  and does not carry evidence; the root is one of its members, not the whole.
- **Tree size**: the number of leaves a head commits to; monotone non-decreasing
  across successive heads (Section 16).
- **Witness**: an independent key holder that co-signs a head; a witness is
  trusted only as far as the reader's policy says, and the co-signature demo
  uses synthetic keys.
- **Vds**: a verifier identity — the key-id hash of the verifier's key — carried
  inside a signed statement so a reader can tell which verifier saw which size.
  It names a verifier, never an algorithm; "a `vds` the reader does not
  recognise" (Section 17.2) means "a verifier outside the reader's policy set",
  and scheme support is a separate question, decided by `resolver`.
- **Checkpoint**: the stored head inside a package (`S8`), recomputed and
  compared; it is not an external anchor.
- **Owner**: the holder of the seal key named in `identity.json`.
- **Policy artefact**: a referenced document whose digest is committed; S18
  resolves it, and does not evaluate its contents.
- **Receipt**: an object from an external log or authority that a verifier can
  check against that system's own rules; a receipt that verifies but covers
  another head is evidence to the contrary (Section 17.2).
- **Generation**: one sealed, headed state of a package. A pending package that
  later gains a receipt produces a second generation; the two are separate
  packages with separate roots (Section 8.2).
- **Per-axis outcome**: the verdict of one axis (structure, integrity, attribution,
  lifecycle) over the whole corpus, as opposed to one check's outcome.
- **Actor allow-list**: the optional list of principal identifiers a verifier
  supplies to S3; a string array, compared exactly, no wildcards or patterns.
- **AC2 / AC4 / AC5**: the anchor-conformance fixtures named in Section 17.4 —
  receipt covers this head; receipt covers another head; no receipt at all.
- **Actor**: the identifier recorded in a lifecycle event's `actor` field. It is
  a name the producer asserts. S3 checks that the field is populated and well
  formed, and checks membership only when the verifier was supplied an actor
  allow-list; without the list, authorisation is unknown rather than assumed.
- **Anchored**: the root has been committed to an external backend and that
  commitment has been *confirmed* by that backend (see Section 8.2).

## 3. Package Structure

A package contains exactly these five required files:

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

`evidence/anchors.json` is optional and sits inside `evidence/`, not at the
package root: it is the producer's declared anchor claim. It is one of the
structural members of `evidence/` (with `merkle.json`, `chain.json`,
`policies.json`), which are exempt from the index rule immediately above, so
**its bytes are not committed by the root**. That is stated here because two
later sections depend on it: Section 8.4 forbids editing it after sealing,
Section 17.1 reads it, and Section 10 lists what follows from it not being
committed. Calling it "covered by the seal" would be false: the seal covers
`identity.json`, `manifest.json` and `lifecycle.json`, and none of them holds a
digest of this file.

## 4. Evidence Root

```
root = SHA-256( canonical_json( sorted( entry.content_hash for entry in index ) ) )
```

Canonical form: RFC 8785 (JCS), i.e. UTF-8, member names sorted by UTF-16 code
unit, no insignificant whitespace, and no Unicode normalization of string
values. The seal (Section 6) uses the same serialization, so one tool can
re-derive both byte strings. The root is stored in `manifest.json` and is the
object that gets anchored, signed, and compared.

The root is **not** a Merkle root: it is one SHA-256 over a sorted list of
30-byte-to-64-byte hex strings. Where a package carries inclusion proofs, the
tree is a different object with its own construction (Section 4.2).

Because the root covers content hashes rather than paths, moving a file
without changing its content does not change the root; changing one byte does.

### 4.1 What commits what

Four objects are easy to conflate in prose, so the scope of each is stated once,
here, and no later section may widen it.

| Object | Commits | Does not commit |
|---|---|---|
| Evidence root (this section) | each index entry's `content_hash`, sorted | paths, media types, index metadata, lifecycle, identity, or any manifest field other than `evidence_root` |
| Seal (Section 6) | RFC 8785 canonical bytes of `identity.json` + `manifest.json` + `lifecycle.json` | the evidence bytes themselves (only their hashes, through `manifest.evidence_root`), paths, index metadata |
| Head (Section 16) | the root, the tree size, and optionally the verifier identity `vds`, inside one signed statement | everything the root does not commit, for the same reasons |
| Anchor (Section 8) | the evidence root alone, submitted to an external backend | identity, lifecycle, seal, paths, metadata |

Consequences, stated rather than implied:

- "The anchor commits the package" is false. An anchor proves that this root
  existed before a point in time; it says nothing about who produced the package
  or which lifecycle events accompanied it.
- What ties identity and lifecycle to the anchored root is the **seal** (whose
  key the reader must trust out of band, Section 6) plus the **head** (whose
  only-grew property Section 16 constrains). A package whose seal is absent, or
  whose key was swapped with the content, has an anchored root that says nothing
  about its actor.
- Because paths and index metadata are outside the root, an attacker holding a
  package can relabel files (move a byte-identical file to another path, change
  `action_type`) and re-derive the index digest without changing the anchored
  root. The seal and the head are what make that visible; the anchor alone does
  not. This is recorded as a limitation, not mitigated by assertion.

### 4.2 Merkle profile (needed by S13)

S13 verifies inclusion proofs only when a package carries them, and a proof is
unverifiable without knowing how leaves and nodes were hashed. Two profiles are
defined, selected by name; a proof whose profile is not named is
`INCONCLUSIVE` (the verifier cannot know which construction produced it).

| Profile | Leaf hash | Node hash | Odd tail | Empty tree |
|---|---|---|---|---|
| `rfc6962` (default) | `SHA-256(0x00 \|\| leaf_bytes)` | `SHA-256(0x01 \|\| left \|\| right)` | promoted, never duplicated | `SHA-256()` |
| `aer1` | `SHA-256(UTF-8 receipt_id)`, no prefix | `SHA-256(left \|\| right)`, no prefix | duplicated level by level | `SHA-256()` |

Duplicating an odd tail under `rfc6962` would let two differently sized trees
share a root; promoting it cannot. `aer1` duplicates on purpose, because the
vectors it serves were generated that way, and it inherits the ambiguity: two
`aer1` trees of different sizes can share a root, so an `aer1` proof pins the
leaf and the path but not the set size. A reader who needs size committed must
read it from the head, not from a proof. A root computed under one profile MUST
NOT be verified under the other — a construction difference, not a bug.


## 5. Verification Procedure

A verifier performs the checks below and reports one outcome per check. A
single `FAIL` makes the verdict `FAIL`; otherwise any `INCONCLUSIVE` makes it
`INCONCLUSIVE`; only all-`PASS` yields `PASS`.

Two invocation modes differ only in what the reader supplies out of band:

- **open** (default): no key, no head. A seal that is absent or unverifiable
  leaves S6 `INCONCLUSIVE`; the package can still be judged on its own bytes, and
  nothing in it is attributable to a named key.
- **strict**: the reader supplies the owner key (and a head where one is
  expected). A missing or non-verifying seal is `FAIL`, because in this mode the
  question asked is "is this the package that key signed", and an absent seal
  answers it in the negative. Strict also fails uncommitted files under
  `evidence/` (S1), which open mode reports as a note.

| ID | Check | Notes |
|---|---|---|
| S11 | strict serialization | runs **before** any parse: UTF-8, no duplicate member names, no raw control characters |
| S1 | package structure | required files present, no undeclared root entries |
| S2 | identity consistency | `agent_id` agrees across files; enum fields valid |
| S3 | lifecycle state machine | chain valid, sequence contiguous, timestamps monotonic; actors authorised **only when an allow-list is supplied** |
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

This rule is about a *second implementation's own* unmapped rule: it must
answer `INCONCLUSIVE` for that dimension, never `PASS`. It is not the same case
as a verifier that does not support a scheme the package names. That one is
answered `FAIL` by policy (Section 17.5), and the two must not be read as
contradicting each other: one is "I have no opinion here", the other is "I
refuse this receipt, as the MMR profile also requires".

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
`base/test-vectors` at kit 1.5.7: 64 receipts across four directories — 21 valid,
36 invalid, 6 anchored and 1 profile case — with four of four directories in
agreement. Our verdicts: 27 accepted (21 valid + 6 anchored), 36 rejected, and
the single `invalid-profile` receipt accepted with the difference recorded as
granularity, not disagreement.

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
commitment, not a content leak: it reveals nothing about bytes nobody can guess.
It does make guesses checkable — anyone holding a candidate package can confirm
whether it is the one anchored — which is why Section 10 lists correlation as
a security consideration rather than claiming the anchor hides anything.

This sentence is about the *anchor request*. The head of Section 16 is a
different object: it carries the root plus the tree size, is signed, and travels
between witnesses, never to the anchor backend, which has no use for it.

### 8.2 Two states, not one

- **pending**: a backend accepted the commitment but it is not yet confirmed
  (an OpenTimestamps calendar attestation before `ots upgrade` matures it
  into a Bitcoin commitment).
- **anchored**: the backend's confirmation has been verified.

A report MUST NOT use the word "anchored" for the pending state.

The pending-to-anchored transition is a **re-emission**, not an edit. The reason
is not that the file is committed — Section 3 says it is not — but that a
generation is defined by the root and the head it carries: a package whose
`state` changed while its root and head did not is a package whose claim exceeds
its evidence. So the producer emits a new generation with the receipt, a new
seal and a new head, and keeps both. A verifier presented with an edited file
sees no integrity failure (nothing committed it) and answers from Section 17's
rules instead: a claim that the receipt chain does not support is `FAIL`, and
one the reader cannot check is `INCONCLUSIVE`. The edit is not *detected*; it is
*tested*.

### 8.3 Backends

Two are specified because one is a single point of censorship:

- **OpenTimestamps calendars** (`POST /digests`, 32-byte body).
- **Nostr relays** (BIP-340 Schnorr signature over a NIP-01 event whose
  `content` carries the root).

Submitting to more than one backend is a SHOULD, not a MUST: availability
differs by jurisdiction.

### 8.4 The proof must not go inside the package

Recording a **new** anchor proof as package evidence changes an input the
producer declared, and the root that was anchored stops matching the claim that
generated it: the root was computed over the index as it stood, and a receipt
added afterwards is a statement about a root the package can no longer
demonstrate. Implementations MUST refuse to add or modify anchor records after
the package has been sealed. This failure is silent and total; it is the single
most likely implementation error in this section.

The rule is about *when*, not *where*: `evidence/anchors.json` has existed since
before this section and is a producer declaration, and — as Section 3 states —
its bytes are not committed by the root. A receipt added after sealing is
therefore **not** caught by S6 or S8. The rule is a producer-side prohibition
precisely because the format cannot enforce it; what a verifier can do is check
the *claim* against the head and the receipt chain (Section 17), so an edited
file either contradicts the head (FAIL) or says nothing the reader must believe.
This is a limitation of the format, not a property of the seal.

## 9. Conformance and Interoperability

An implementation is conformant if it: (a) reproduces the committed test
vectors, (b) reports `INCONCLUSIVE` rather than `PASS` when a check cannot be
resolved, and (c) never accepts a foreign-format document as its own.

Two definitions that were previously left implicit, and therefore became
implementation choices rather than specification choices:

- **"First failing check" means the lowest-numbered failing check.** The printed
  report does not run in check order (measured on a duplicated package: S11, S1,
  S2, S3, S4, S12, S7, S8, S5, S6), so "the first failure" is undefined until
  this rule is fixed. Both the corpus generator and the per-axis report use this
  rule; any other reading produces a different, equally defensible answer for
  the same bytes.
- **`evidence/index.json` admits exactly `entries` and `schema`.** The metadata
  digest covers each entry's path, type, note and action digest, so a member
  added at the top level of the index sits outside every check: measured, a
  package with an extra `generated_at` member verified PASS before this rule
  existed. An undeclared member is now refused (S7), because a reader that
  trusts it would be trusting a value no check covers.

Interoperability with AER-1 receipts is defined by an explicit mapping
(Appendix A), not by similarity of intent. The reference implementation
demonstrates both directions: emitting AER-1 receipts that the AER-1
publisher's own runner accepts, and judging external AER-1 receipts
with 27 accepted (21 valid and 6 anchored) and 36 rejected, out of 64. The accept side is the control: by
Section 5.1 a rejection count alone proves nothing, and the 28 documents from two
unrelated protocols that were all rejected are therefore not quoted as interop
evidence — they appear only in the corpus report, where the denominator is stated.

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
- **The anchor claim is not committed.** `evidence/anchors.json` is a structural
  member outside the root (Section 3), so a receipt written into it after sealing
  is invisible to S6 and S8, and two readers can hold packages that differ only
  in that file and verify both. The verifier's defence is to check the claim
  against the head (Section 17); a reader who needs the claim itself committed
  must ask for the receipt out of band.
- **Metadata relabelling.** The root covers content hashes, so a package holder
  can change paths, `media_type` or `action_type` and re-derive the index digest
  while the anchored root stays valid (Section 4.1). The seal and the head are
  the only things that expose this.
- **Backend trust.** An OTS calendar or a Nostr relay can refuse, delay, or
  equivocate; a single-backend `anchored` verdict inherits that backend's
  availability and honesty, and block depth is the reader's policy.
- **Key lifecycle.** `REVOKED` is an outcome (Section 7), but no rotation, no
  revocation distribution and no key history are specified; a rotated key
  without history makes older packages look tampered.
- **Resource exhaustion.** Nothing here bounds entry counts, policy nesting depth
  or single-file size. A verifier MUST apply local limits and report a package
  that exceeds them as `FAIL` (refused), never `PASS`.
- **Verification side channels.** Signature and MAC comparison SHOULD be
  constant-time; a timing-observable comparison undermines S6 whatever the
  algorithm.
- **Privacy.** Evidence bytes go to whoever verifies the package, and the format
  has no redaction mechanism; a producer that needs one must commit to a digest
  of redacted content and say so.
- **Hash and signature agility.** SHA-256 and Ed25519 appear as *the* primitives.
  A transition needs versioned algorithm identifiers, which this document does
  not define.
- **Witness independence.** Two distinct keys are not two distinct parties; a
  reader who counts signatures instead of checking who holds them is trusting
  one operator twice. The co-signature demo uses synthetic keys, and
  Implementation Status says so.
- **Seal stripping.** Removing the seal turns PASS into INCONCLUSIVE rather than
  FAIL; a reader who treats "not FAIL" as "acceptable" has inverted the outcome
  set. `strict` mode (Section 5) exists for readers who require the seal.

## 11. IANA Considerations

This document requests no IANA action. No media type registration is
requested at this version.

## 12. References

Normative: [RFC2119], [RFC8174], [RFC3339], [RFC8032], [RFC2104].

Informative: [RFC3161] (external timestamp tokens, S16), [AER1] (`draft-zambo-aer1-26`,
the receipt format this mapping targets), [BIP340] (Schnorr signatures used by
the Nostr backend), [NIP01] (Nostr event serialization).

## Appendix D. Carriage in a verdict record

A package verdict can be carried by a `verdict-record/1` record without changing
either format. Our three outcomes map to that record's **state** axis, not to its
`check.result` axis:

| this document | verdict-record state | why |
|---|---|---|
| `PASS` | released | all applicable checks held |
| `INCONCLUSIVE` | held | an input is missing; the claim is neither supported nor refused |
| `FAIL` | refused | a check refused the bytes — either a contradiction or a capability the verifier does not implement (fail-closed by policy; Section 17.5) |

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
for carrying an unregistered value **in an extension member**: registration
governs shared meaning, never acceptance. Every vocabulary check is performable
from the record's own bytes.

The rule does not reach enumerated fields this document defines, whose values
decide what the verifier may conclude. An unknown `state` in an anchor record is
such a field and is rejected (Section 17.2, rule 4); an unknown
`disposition_code` on an evidence entry is an extension value and is not.

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

A head statement is one JSON object with four members: `head` (the member name;
its **value** is the evidence root of Section 4, not a nested head), `role`
(`owner` or `witness`), `tree_size`, and `vds`. It is signed over RFC 8785
canonical bytes of that object, with `tree_size` and `vds` omitted only when the
signer did not observe them. `tree_size` and `vds` sit inside the signed
statement, so neither the size nor the verifier identity can be swapped after
signing.

Three rules bind the tiers, and each answers a question the cited drafts leave open:

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

Proposed additions, all optional, so existing packages and the 32-case corpus
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
   requires rejecting a receipt whose `vds` names a verifier outside the reader's
policy set, and
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
MMR receipts profile's requirement to reject a receipt whose VDS the reader
does not recognise.
To keep that choice from erasing the distinction, the verifier now carries a
report-level `unsupported` list naming the checks that failed this way: the
verdict stays FAIL, but a reader can separate "could not check" from "checked and
refused". The two cited drafts answer the same question differently
(`draft-gruszka-scitt-statement-identification-04` reports UNSUPPORTED as its own
class, `draft-nestorov-scitt-p10-underdetermination-03` HALTs); this document
reports both, which is what lets the sentence mean "cannot check" at all.

## Implementation Status

_As of 2026-11-27, repository `bf91c81`, reference verifier 0.5.5._

- Implemented and re-runnable: the 19-check procedure, the 32-case corpus with a
  validator, anchor handling (`evidence-merkle` today; OpenTimestamps + Nostr
  exist as tools, and `pending` vs `anchored` is proposed in Section 17 but not
  read by the verifier),
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
| Anchoring | section defined, SDK ships Nostr + OTS | two backends specified; both exist as tools, neither is on the verifier's default path |

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
