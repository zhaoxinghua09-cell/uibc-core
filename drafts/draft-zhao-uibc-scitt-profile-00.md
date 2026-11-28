Agent Evidence Packages as SCITT Statements
=========================

# Abstract

This document profiles [RFC9943] and [RFC9942] for one narrow application:
registering an *agent evidence package* in a transparency service, and reading
the resulting receipt. It does not define a transparency service, a receipt
format, or a tree construction; those are [RFC9943], [RFC9942], and the
verifiable-data-structure profiles built on it. What this profile adds is the
part the published documents leave to the application: **what exactly is
registered**, **what a receipt then proves about the package**, and **what the
receipt does not prove**, stated once so that two readers cannot disagree about
it while both being right about [RFC9942].

Status: individual draft dated 2026-11-27, not submitted, not adopted by any
working group. It supersedes nothing. The companion document it profiles is
`draft-zhao-uibc-evidence-chain` (this repository), which defines the package
layout that this profile registers. Dates in this document are stated as of that
date: [RFC9942] and [RFC9943] were published 2026-06-30, and the two receipt
profiles in Section 10 were read at their November 2026 revisions.

## 1. Introduction

[RFC9943] defines a transparency service (TS): issuers submit signed statements,
the TS registers them in a verifiable data structure and returns a receipt, and a
consumer checks the receipt against a signed statement and a policy they trust.
[RFC9942] defines what that receipt is: a COSE Sign1 whose detached payload is a
tree root, whose `vds` header fixes the tree algorithm and hash, and whose `vdp`
header carries the proof.

Both documents are deliberately silent about the payload. A statement is
"a COSE_Sign1 with a payload the application understands", and the receipt proves
"this statement was registered", not "this payload means what its author says".
That silence is correct at their layer and it is where every implementation
diverges: one team registers a hash of the whole package, another registers the
hash of a manifest, a third registers the manifest bytes themselves and keeps the
evidence elsewhere. All three can hold valid receipts and disagree completely
about what a passing check means.

This profile fixes one of those choices, for one payload type, and states the
consequence:

- what the issuer registers (Section 4);
- how a verifier reconstructs the registered value from bytes it holds (Section 5);
- what a passing receipt check therefore does and does not establish (Section 6);
- what stays outside the profile (Section 7).

The two receipt profiles the working group added in November 2026 are listed in
Section 10, not restated here: this document does not choose a tree construction,
it only refuses to invent one.

Everything it fixes is a *choice*, not a deduction from [RFC9943]. The choice is
narrow on purpose: a profile that decided less would not remove the disagreement
it exists to remove.

## 2. Conventions and Terminology

The key words MUST, MUST NOT, REQUIRED, SHOULD, and MAY are to be interpreted as
described in [RFC2119] and [RFC8174] when, and only when, they appear in capital
letters.

Terms from [RFC9943] and [RFC9942] are used with the meanings given there:
*statement*, *transparency service*, *receipt*, *verifiable data structure*,
`vds`, `vdp`. Terms from the companion package document are used as defined
there: *package*, *evidence root*, *seal*, *head*, *anchor claim*.

Two terms are specific to this profile:

- **Registered value**: one exact byte string — the RFC 8785 serialization of the
  four-member object in Section 4.2. Where this document says "the object", it
  means the members; where it says "the value", it means those bytes. The
  distinction matters at Section 5 step 2, which compares bytes to bytes, and it
  is the only sense in which this profile uses the term.
- **Package holder**: whoever holds the package bytes. The holder need not be the
  issuer, and need not be the TS.

## 3. What the profile does not change, and what it must decide

This profile adds no header parameter, registers no value, and amends no
procedure in [RFC9942]. A transparency service that implements [RFC9943] and
[RFC9942] needs no extension to register a statement from an issuer that follows
this document: it receives a COSE_Sign1, registers it, and returns a receipt.

The one behaviour this profile leans on is not a new requirement — it is what a
transparency service does with any statement: register the bytes it received. A
service that re-serialises a payload breaks the commitment, and the issuer
detects it at Section 5 step 2 rather than assuming it did not happen.

The obvious objection is that Section 4.2 does define a payload, and a payload
definition is a format. It is, and that is the point rather than an oversight.
[RFC9942] and [RFC9943] leave the payload to the application; an application
profile of a protocol that leaves a field open must say what goes in that field,
or the two documents say nothing about each other. The alternative was tried
first in this repository — a document defining a package format and asking a
reader to infer how it relates to a transparency service — and the result was
three readers reaching three conclusions. Fixing four members is the smallest
decision that removes that ambiguity; anything less leaves the question of
"registered what?" open, which is the question this document exists to answer.

What stays untouched is the machinery: the receipt, its headers, the tree
constructions, and the security considerations all remain those of [RFC9942]
and [RFC9943], and none of them is restated or redefined here.

## 4. Registration

### 4.1 Statement shape

The statement is a COSE_Sign1 as defined in [RFC9943]. Its protected header
carries the issuer's signing parameters; its payload is the registered value of
Section 4.2. The profile does not constrain the issuer's key type beyond what
[RFC9943] requires, and does not require any `CWT Claims` content: identity
resolution is the TS's policy question, not this profile's.

### 4.2 The registered value

The registered value is the RFC 8785 canonical JSON serialization of exactly four
members:

```
{
  "profile":   "uibc-scitt/1",
  "root":      "<64 lowercase hex>",   // the package's evidence root
  "count":     <integer>,              // number of index entries the root covers
  "agent_id":  "<string>"              // the producer's identifier for the agent
}
```

Rules, each with the reason it exists:

1. **`root` is the evidence root of the package, not a hash of the package
   folder.** A hash of the folder would make every packaging detail
   (file order, timestamps, compression) part of the registered value, and two
   parties holding the same evidence would register different values.
2. **`count` is inside the value.** A root over 12 content hashes says nothing
   about how many entries produced it; a verifier that accepts a package with 11
   or 13 entries and a matching root would be accepting a truncated or padded
   list. `count` is the only member that makes the length checkable after the
   fact.
3. **`agent_id` is inside the value.** The root covers content hashes only; it
   does not say whose evidence this is. Without this member a receipt for one
   producer's package would verify equally for another producer's package with
   the same bytes, which is the exact confusion an audit trail exists to
   prevent.
4. **`profile` is inside the value.** It states which reading of the payload
   applies, so a future profile with a different member set cannot be confused
   with this one by a verifier that supports both.

The value MUST be serialized per [RFC8785] before signing, and the same bytes
MUST be what is registered. A TS that re-serializes the payload has broken the
commitment; the issuer detects this by checking that the receipt's payload equals
its own bytes (Section 5, step 2).

This member set is a *decision of this profile*, not a reading of [RFC9942]:
the RFC fixes neither members nor their names, and a different profile of the
same receipts may fix a different set. What makes this one checkable is that it
is stated in one place, so a disagreement about "what was registered" is a
disagreement with this text rather than an inference from silence.

### 4.3 What travels with the package, and what does not

The evidence bytes do **not** go to the TS. Two reasons, both practical:

- a transparency service is an append-only public log; publishing raw agent
  evidence into it publishes whatever the evidence contains, including personal
  data, and [RFC9943] does not give the TS a confidentiality story;
- evidence can be large and mutable in distribution; the registered value is
  32-to-64 bytes plus a short header, which is the unit a log should carry.

Therefore the package holder keeps the evidence and the index, and the receipt
alone is not enough to check anything: a verifier needs the package.
This is stated because the alternative reading — "the log holds my evidence, so
the receipt proves my evidence" — is the most common misreading of a
transparency service, and it is false.

## 5. Verification

A verifier holds a package and a receipt, and does the following. Steps 1–4 are
required; steps 5–6 are required only when the inputs named are present.

The package layout belongs to the companion document, but step 1 cannot be
followed on a pointer alone, so the three facts it needs are restated here and
this section can be read without that document: the package carries its evidence
under `evidence/`, one file per entry; `evidence/index.json` lists, for each entry,
`path`, `media_type` and `content_hash`; and the evidence root is the hash over
the sorted content hashes, with the entry count taken from the index. Everything
else about the layout — naming, optional members, seals — is not needed to check
a receipt, and a verifier that only reads those three facts is conformant to this
profile even if it knows nothing else about the package.

1. **Reconstruct the root.** From the package's `evidence/index.json` and the
   evidence bytes, recompute the evidence root over the sorted content hashes,
   and refuse if any declared file is missing or any undeclared file sits under
   `evidence/`. The verifier MUST NOT take the root from the package's own
   `manifest.json` without recomputing it: that field is what is being checked.
2. **Reconstruct the registered value.** Build the four-member object of
   Section 4.2 from the recomputed root, the recomputed entry count, the
   `agent_id` and the profile string, serialize with [RFC8785], and require the
   receipt's payload to equal the resulting bytes exactly. Build and compare
   bytes; do not compare parsed objects, because two parsers that agree on meaning
   can disagree on bytes and the commitment is over bytes. A mismatch is a
   failure of the receipt, not a warning: it means this receipt was issued for
   different bytes.
3. **Check the receipt against the registered value.** Verify the COSE signature,
   the inclusion proof, and the `vds` value per [RFC9942]. The service's signing
   key is obtained out of band. A signature checked only against the key the
   receipt itself carries establishes self-consistency, not that the service
   issued it; a verifier in that position MUST report the issuer question as
   unchecked, and a receipt whose key is outside the verifier's trusted set MUST
   be refused as an untrusted issuer rather than reported as a pass with a
   warning. The verifier MUST
   reject a receipt whose `vds` it does not support; "I do not implement this tree"
   is a rejection and MUST be reported as an unsupported scheme, not as evidence
   that the package is false. The two are different claims and a report that
   merges them is unreadable to whoever has to act on it.
4. **Check the anchor claim against the receipt.** The package may carry an
   anchor claim (the companion document's `evidence/anchors.json`). A claim that
   says "anchored" MUST carry a receipt that verifies as above **for this
   registered value**; a receipt that verifies but covers another value is
   evidence to the contrary, not missing evidence. A claim that says "pending"
   carries no receipt and MUST NOT be reported as anchored.
5. **Check the tree size, when the verifier holds one.** If the verifier has a
   previously trusted size for this log, the receipt's proof MUST be consistent
   with it. If the verifier holds no size, it MUST NOT invent one: an inclusion
   proof alone does not say when the registration happened.
6. **Check monotonicity, when the verifier holds a previous head.** If two
   receipts for the same producer are presented, sizes MUST be non-decreasing and
   a grown size MUST come with a changed root. Equal sizes with different roots
   are a fork and MUST be reported as one.

## 6. What a passing check establishes

Stated once, because this is the sentence the profile exists to make
unambiguous:

> A passing check establishes that the holder's package reproduces the
> four-member value that a transparency service registered, and that the receipt
> chains to that registration under a tree construction the verifier supports.
> It does not establish that the evidence is true, complete, or about the agent
> it names; that the issuer was authorised to register it; that the registration
> happened at any particular time; or that any real-world event followed.

Each clause corresponds to a step above: step 1 binds the bytes, step 2 binds
identity and length, step 3 binds the log, step 5 is where "when" would live and
is absent by design.

The value of the check is narrow and sufficient for one question: *did this
package exist in this form, and was it registered?* That is the question an audit
trail answers when it is asked months later and the producer's own records are
gone.

## 7. What stays outside the profile

Named so that a reader does not infer them from silence:

- **Evidence confidentiality.** The profile keeps evidence off the log, but says
  nothing about how a holder protects it.
- **Authorisation.** Who may register on an agent's behalf is a policy question;
  [RFC9943] has the vocabulary for it and this profile does not decide it.
- **Time.** A receipt of registration carries no time. Only a timestamp token
  from an authority the verifier trusts, or a consistency proof against a
  previously trusted size, orders anything.
- **Multiple logs.** A package may carry receipts from several services. Which
  combination is sufficient is policy; the profile requires only that each
  receipt verify for the same registered value, and that disagreement between
  them be reported rather than resolved by preference.
- **Payload semantics beyond the four members.** Nothing here says what the
  evidence means, and nothing here may be cited to say it.

## 8. Security Considerations

Inherited from [RFC9942] and [RFC9943] and not restated: signature algorithm
requirements, proof validation, and the TS's own trust model.

Specific to this profile:

- **The registered value is small on purpose, and therefore says little.** Four
  members bind bytes, length, producer and profile. Everything else is
  unauthenticated by the receipt and must be checked from the package. A verifier
  that treats a valid receipt as a statement about the whole package has
  over-read it.
- **`count` is a defence against truncation, not against substitution.** A
  party holding a different evidence set with the same root would need a
  second-preimage of SHA-256; a party dropping entries changes the root and the
  count together, so both must match.
- **Registration is public.** Anyone who can read the log learns that this
  producer registered a value of this size at some position. If that fact is
  sensitive, the producer must know it before registering; the profile provides
  no unlinkability.
- **Evidence bytes are attacker-supplied.** A verifier that parses evidence
  content (images, archives, PDFs) exposes itself to whatever that content does.
  The profile's checks are over hashes; a verifier MUST NOT open evidence bytes
  to decide the verdict.
- **A TS that signs a value it did not receive** breaks the only binding this
  profile has. That is a TS misbehaviour, and it is detectable only by a verifier
  that checks step 2 against its own bytes — which is why step 2 exists.

## 9. IANA Considerations

This document requests no IANA action. It registers no `vds` value: the values
this profile reads are those the [RFC9942] profiles register, and a profile that
minted its own would be asking a verifier to support a tree nobody else uses.

## 10. References

Normative: [RFC2119], [RFC8174], [RFC8785], [RFC9942], [RFC9943].

Informative: [RFC3161] (the only mechanism here that produces a time),
[RFC9162] (a tree construction with leaf/interior domain separation, which the
receipt profiles in circulation do not all use — the difference matters when
comparing roots across implementations), and the two receipt profiles read at
their 2026-11 revisions:
`draft-ietf-scitt-receipts-ccf-profile-06`,
`draft-ietf-scitt-receipts-mmr-profile-00`.

The two numbers are not a mistake: `-ccf-profile` is a document that has been
iterated since 2023 and stands at revision 06, while `-mmr-profile` is a new
document whose first revision is 00. Both were read in the same month, which is
why they appear together with different numbers.

Neither is normative here, and that has a consequence for how far this profile
can go: the shape of the inclusion proof (`vdp`) is defined by the verifiable-data-structure
profile a service applies, not by [RFC9942]. A verifier that checked a `vdp` without
first choosing one of those profiles would be guessing at its encoding. This
document therefore stops at the step-3 boundary and says so, rather than defining
a `vdp` of its own — which would be exactly the "new format" this profile exists
to avoid.

## Appendix A. Mapping to the companion package document

| This profile | Companion document |
|---|---|
| Registered value `root` | §4 evidence root (SHA-256 over sorted content hashes) |
| Registered value `count` | number of entries in `evidence/index.json` |
| Registered value `agent_id` | `manifest.json` `agent_id` |
| Receipt | carried by the anchor claim, `evidence/anchors.json` |
| Step 4's "evidence to the contrary" | §8.4 and Appendix G.2, rule 3 |
| Step 6 fork check | head chain (`tools/cosign_head.py`), size monotonicity |

The companion document keeps its own vocabulary (`head`, `seal`,
`verifier_id`). None of those names is used here, because none of them is a
[RFC9942] or [RFC9943] term, and this profile's job is to speak in theirs.

## Appendix B. Re-running the claims in this document

The steps above are not prose: `uibc_core/profile.py` implements Sections 5 and 4.2,
and a reader can run them against the shipped example package without a
transparency service:

```
git clone https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core && git checkout feat/standards-exceed-20261125
python tools/verify_profile.py examples/demo.uibc --selftest
```

`--selftest` prints the runs the code distinguishes: a receipt for this package, the
same package with a receipt for other bytes, a receipt from a tree this code does
not implement, a receipt with no proof, and a receipt signed by a key outside the
trusted set. The verdicts differ (`PARTIAL_INCLUSION_UNCHECKED`,
`FAIL_VALUE_MISMATCH`, `UNSUPPORTED_SCHEME`, `FAIL_MALFORMED`,
`FAIL_UNTRUSTED_ISSUER`), which is the point: a verifier that prints one word for
all of them cannot be acted on. `conformance/profile/cases.json` holds the same
cases as bytes, and `python tools/run_profile_vectors.py` replays them without
re-deriving anything.

Four limits of that code, stated rather than implied by it passing:

- **It never returns `OK`.** The inclusion proof (`vdp`) is not evaluated and the
  best outcome is `PARTIAL_INCLUSION_UNCHECKED`. The repository does have a Merkle
  implementation (`uibc_core/merkle.py`) that checks RFC 6962 proofs; what it does
  not have is an encoding to read a `vdp` out of, because [RFC9942] leaves the
  shape to the verifiable-data-structure profile a service applies (Section 10).
  Checking it without fixing one would mean inventing a format of our own. A verifier that reports `OK` while guessing at `vdp`
  is worse than one that reports `PARTIAL`.
- **`vds` values are supplied by the caller.** The registry entries that would pin
  them are still `TBD`, so supporting a tree is a decision a verifier makes and
  states, not something this document can hand it.
- **Issuer trust is the caller's input.** The code can refuse a key outside a
  trusted set, but it cannot invent that set: without one, the issuer question is
  reported as `NOT_CHECKED`, and a receipt any stranger could mint still reads
  `PARTIAL_INCLUSION_UNCHECKED` rather than `OK`.
- **No live service was involved.** Step 3 is checked against synthetic receipts and
  against AER-1's published receipt corpus as a consumer; no case registers
  anything in a real log. That gap is written here instead of being left for a
  reader to discover from a green test run.

The rest of the repository is unchanged by this profile and still runs:

```
python tools/axis_report.py       # 32 cases, expectation per case in expected.json
python -m pytest -q               # ~2,100 tests
```
