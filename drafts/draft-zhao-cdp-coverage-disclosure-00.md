---
title: "Coverage Disclosure for Agent Evidence Verifiers"
abbrev: "CDP-1"
docname: draft-zhao-cdp-coverage-disclosure-00
category: info
ipr: trust200902
area: Security
workgroup: SCITT
keyword: [agent, evidence, receipt, coverage, conformance]
stand_alone: yes
pi: [toc, sortrefs, symrefs]
author:
  - name: Xinghua Zhao
    organization: Independent
    email: zhaoxinghua09-cell@users.noreply.github.com
normative:
  RFC2119:
informative:
  RFC9052:
  RFC6962:
  SCITT-ARCH: RFC-to-be
  EQR:
    title: "Evidence Qualification Receipts: Conformance Profile (eqr-core-1)"
    author:
      - name: G. Wang
    date: 2026-10
  ASQAV:
    title: "Compliance Profile of Signed Action Receipts for AI Agents"
    author:
      - name: Marques
    date: 2026-09
---
# Coverage Disclosure for Agent Evidence Verifiers

## Abstract

Verifiers of agent evidence publish what they accept and what they reject. They rarely publish
what they never test. A relying party who is told "1,280 of 1,280 substitutions were detected"
learns nothing about the requirements that no case exercises, and therefore cannot price the risk
that remains.

This document defines a **coverage ledger**: a machine-readable, signable object in which a
verifier states, per requirement, whether a test exercises it, and — where none does — why not,
who owns the gap, and when it will be reviewed. It does not define a receipt format. It defines
the disclosure that any receipt format can carry.

## Status of This Memo

This Internet-Draft is submitted in full conformance with the provisions of BCP 78 and BCP 79.
Internet-Drafts are working documents of the Internet Engineering Task Force (IETF). This document
is intended to be Informational.

## 1. Introduction

Three practices now coexist in agent-evidence work:

1. **Formats** describe what a receipt contains (SCITT profiles, capsule formats, audit-trail schemas).
2. **Vectors** describe what a verifier must accept or reject (conformance corpora, mutation suites).
3. **Scores** describe how often a verifier was right on a given corpus.

None of the three states *what the verifier does not check*. A conformance corpus is bounded by
its authors' imagination; a mutation suite is bounded by its mutations; a pass rate is bounded by
the cases run. The untested remainder is invisible, and invisibility is the failure mode that
regulated industries long ago named: every functional-safety regime (DO-178C, ISO 26262,
IEC 62304, ASPICE) requires bidirectional requirement-to-test traceability and treats a
requirement without a test as a first-class, visible state.

Agent evidence has the formats and the scores. It does not have the ledger.

## 2. Conventions and Definitions

The key words MUST, MUST NOT, SHOULD, and MAY are to be interpreted as described in [RFC2119].

**Requirement**: a normative statement the verifier claims to enforce.
**Exercise**: a test, vector, or attack that fails when the requirement is violated.
**Gap**: a requirement with no exercise.
**Coverage ledger**: the object defined in Section 4.
**Disclosure**: the act of publishing a ledger, including its gaps.

## 3. What a Ledger Does and Does Not Establish

A ledger establishes that the publisher has *enumerated* its requirements and *declared* the
status of each. It does not establish that a requirement list is complete, that an exercise is
strong, or that a declared gap is the only gap.

Those three limits are addressed by making the first of them an entry in the ledger itself
(Section 5, CDP-R6), rather than a caveat in prose.

## 4. The Coverage Ledger Object

A ledger is a JSON object [RFC8259] with media type `application/cdp+json`.

```
{
  "schema": "cdp-1",
  "subject": { "name": "...", "version": "...", "commit": "...", "measured_at": "..." },
  "entries": [
    { "id": "S1", "kind": "CHECK|REQUIREMENT|VECTOR|SUITE",
      "statement": "...", "statement_sha256": "...",
      "status": "EXERCISED|UNTESTED|EXEMPT|NOT_PUBLIC",
      "tests": ["..."], "evidence": ["..."],
      "owner": "...", "review_by": "YYYY-MM-DD", "reason": "..." }
  ],
  "summary": { "total": n, "exercised": n, "untested": n, "exempt": n, "not_public": n,
               "disclosure_completeness": x, "named_gap_ratio": y },
  "signature": { ... }
}
```

`statement_sha256` binds the entry to the exact wording it discloses, so that editing a
requirement invalidates the ledger rather than silently changing what was claimed.

## 5. Disclosure Requirements

**CDP-R1.** A ledger MUST assign a status to every entry. An entry without a status invalidates
the ledger.

**CDP-R2.** An entry with status `EXERCISED` MUST name at least one exercise.

**CDP-R3.** An entry with status `UNTESTED` or `EXEMPT` MUST carry a `reason`, an `owner`, and a
`review_by` date. "Not tested" alone is non-conformant: the reason, the accountability, and the
review horizon are part of the disclosure.

**CDP-R4.** A ledger SHOULD cover every requirement the verifier claims to enforce. Where a
requirement is enforced but not enumerated, the omission is itself a gap and SHOULD appear as an
entry stating that enumeration is incomplete.

**CDP-R5.** `summary` counts MUST equal the entries. A summary that does not recompute from the
entries invalidates the ledger. Implementations MUST recompute; they MUST NOT trust the summary.

**CDP-R6.** The completeness of the requirement enumeration MUST itself be an entry. A ledger
that states "every requirement is enumerated" without an exercise for that statement is
declaring an untested requirement, and MUST say so.

**CDP-R7.** When the ledger covers a verifier the publisher does not control, entries the
publisher cannot observe MUST be `NOT_PUBLIC` with a stated reason. A peer ledger MUST NOT
convert silence into a pass.

## 6. Verdict Semantics

A ledger consumer returns two separate outputs, and MUST NOT collapse them:

- `ledger_conformant`: whether the object satisfies Section 5;
- `coverage` : the recomputed summary.

An object that violates Section 5 MUST NOT be reported as "pass". It is non-conformant, in the
sense of "the disclosure was not made", which is distinct from "the verifier is wrong".

A consumer MAY rank verifiers by `false_accept` only among publishers whose ledgers are
conformant. Comparing a rate with a disclosure to a rate without one compares a bounded claim
with an unbounded one.

## 7. Metrics

- `disclosure_completeness` = (total - not_public) / total. Share of entries on which a public
  disposition exists.
- `named_gap_ratio` = untested entries carrying reason, owner and review_by / untested entries.
- `false_accept` = mutations accepted / mutations applied, reported per mode (open, pinned,
  head-pinned). This metric is defined elsewhere; it is repeated here only because ranking
  requires both numbers.

No composite score is defined. A single number invites weighting arguments; the axis this
document adds is a gate, not a weight.

## 8. Relationship to Other Documents

This document does not modify [RFC9052], SCITT architecture, or any receipt profile. A ledger
MAY be carried as an extension in a receipt, referenced by digest from one, or published beside
one. Relationship to conformance profiles such as EQR [EQR] and compliance profiles such as
ASQAV [ASQAV] is additive: those documents define what a conformant object is; this document
defines what a verifier says it does not check.

## 9. Security Considerations

A ledger can lie by omission: a publisher may enumerate an easy subset, declare it fully
exercised, and leave the hard requirements out. Three mitigations are specified, none sufficient
alone: R4 makes omission a declared gap; R6 makes enumeration completeness an entry; and the
signature plus an external timestamp make retroactive edits detectable.

A ledger can also go stale: requirements change and the ledger does not. `statement_sha256`
turns that into a detectable failure at the next check rather than a silent divergence.

## 10. IANA Considerations

This document requests registration of the media type `application/cdp+json` in the "Media Types"
registry.

## 11. References

See the XML source for the full reference list: [RFC2119], [RFC8259], [RFC9052], [RFC6962],
[EQR], [ASQAV].

## Appendix A. Example Instance

```json
{
  "schema": "cdp-1",
  "subject": {"name": "uibc-core", "version": "0.4.0", "measured_at": "2026-11-19T06:47:12+08:00"},
  "entries": [
    {"id": "S4", "kind": "CHECK", "statement": "flipping one byte in evidence is detected",
     "status": "EXERCISED", "tests": ["tools/check_matrix.py::S4"],
     "evidence": ["docs/CHECK-MATRIX.md"]},
    {"id": "R1", "kind": "REQUIREMENT",
     "statement": "every normative MUST is enumerated with a test mapping",
     "status": "UNTESTED", "tests": [],
     "owner": "maintainer", "review_by": "2026-12-31",
     "reason": "requirement-level enumeration is not yet complete; disclosed rather than implied"}
  ],
  "summary": {"total": 2, "exercised": 1, "untested": 1, "exempt": 0, "not_public": 0,
              "disclosure_completeness": 1.0, "named_gap_ratio": 1.0}
}
```

## Appendix B. Implementation Status

The publisher maintains a reference generator and validator for this object. On 2026-11-19 it
produced a ledger of 20 entries (18 checks, 1 vector suite, 1 requirement-level entry), of which
19 were `EXERCISED` and one — the enumeration of normative statements — was `UNTESTED` with an
owner and a review date. A validator re-derives the summary and exits non-zero on any violation
of Section 5. Peer ledgers for three other projects were generated from public facts only, with
unobservable rows marked `NOT_PUBLIC`.
